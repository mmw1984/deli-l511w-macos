package com.deli.print

import android.content.SharedPreferences
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.pdf.PdfRenderer
import android.os.Handler
import android.os.Looper
import android.os.ParcelFileDescriptor
import android.print.PrintAttributes
import android.print.PrinterCapabilitiesInfo
import android.print.PrinterId
import android.print.PrinterInfo
import android.printservice.PrintJob
import android.printservice.PrintService
import android.printservice.PrinterDiscoverySession
import java.io.File
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.math.abs
import kotlin.math.min

data class Geometry(val name: String, val width: Int, val height: Int, val physicalWidth: Int, val physicalHeight: Int, val offset: Int = 96) {
    companion object {
        fun forMedia(id: String?) = when (id) {
            PrintAttributes.MediaSize.ISO_A5.id -> Geometry("A5", 3312, 4768, 3496, 4960)
            PrintAttributes.MediaSize.NA_LETTER.id -> Geometry("Letter", 4896, 6400, 5100, 6600)
            "DeliPhoto" -> Geometry("Photo4x6", 2416, 3590, 2416, 3590, 0)
            else -> Geometry("A4", 4768, 6824, 4960, 7015)
        }
    }
}

class DeliPrintService : PrintService() {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val timer = Executors.newSingleThreadScheduledExecutor()
    private data class Running(val cancelled: AtomicBoolean = AtomicBoolean(), val socket: AtomicReference<Socket?> = AtomicReference())
    private val running = ConcurrentHashMap<android.print.PrintJobId, Running>()

    override fun onCreatePrinterDiscoverySession(): PrinterDiscoverySession = object : PrinterDiscoverySession(), SharedPreferences.OnSharedPreferenceChangeListener {
        private val store = Printers(this@DeliPrintService)
        private var active = false
        private fun refresh() {
            if (!active) return
            val items = store.list().map { printer ->
                val id = generatePrinterId(printer.host)
                val caps = PrinterCapabilitiesInfo.Builder(id)
                    .addMediaSize(PrintAttributes.MediaSize.ISO_A4, true)
                    .addMediaSize(PrintAttributes.MediaSize.ISO_A5, false)
                    .addMediaSize(PrintAttributes.MediaSize.NA_LETTER, false)
                    .addMediaSize(PrintAttributes.MediaSize("DeliPhoto", "4x6 (experimental)", 4027, 5983), false)
                    .addResolution(PrintAttributes.Resolution("600", "600 dpi", 600, 600), true)
                    .setMinMargins(PrintAttributes.Margins(160, 160, 160, 160))
                    .setColorModes(PrintAttributes.COLOR_MODE_COLOR or PrintAttributes.COLOR_MODE_MONOCHROME, PrintAttributes.COLOR_MODE_COLOR)
                    .setDuplexModes(PrintAttributes.DUPLEX_MODE_NONE, PrintAttributes.DUPLEX_MODE_NONE).build()
                PrinterInfo.Builder(id, "${printer.name} (${printer.host})", PrinterInfo.STATUS_IDLE).setCapabilities(caps).build()
            }
            val valid = items.map { it.id }.toSet()
            removePrinters(printers.map { it.id }.filter { it !in valid })
            addPrinters(items)
        }
        override fun onStartPrinterDiscovery(priorityList: MutableList<PrinterId>) { active = true; store.preferences.registerOnSharedPreferenceChangeListener(this); refresh() }
        override fun onStopPrinterDiscovery() { active = false; store.preferences.unregisterOnSharedPreferenceChangeListener(this) }
        override fun onValidatePrinters(printerIds: MutableList<PrinterId>) = refresh()
        override fun onStartPrinterStateTracking(printerId: PrinterId) = refresh()
        override fun onStopPrinterStateTracking(printerId: PrinterId) {}
        override fun onDestroy() { onStopPrinterDiscovery() }
        override fun onSharedPreferenceChanged(preferences: SharedPreferences?, key: String?) { main.post { refresh() } }
    }

    override fun onRequestCancelPrintJob(job: PrintJob) {
        running[job.id]?.let { it.cancelled.set(true); try { it.socket.get()?.close() } catch (_: IOException) {} }
        job.cancel()
    }
    override fun onPrintJobQueued(job: PrintJob) {
        val info = job.info
        val source = job.document.data
        if (source == null) { job.fail("Cannot open PDF"); return }
        val task = Running()
        running[job.id] = task
        job.start()
        worker.execute {
            var cachedPdf: File? = null
            var cachedStream: File? = null
            fun checkCancelled() { if (task.cancelled.get()) throw IOException("Cancelled") }
            try {
                val pdfFile = File.createTempFile("deli-", ".pdf", cacheDir).also { cachedPdf = it }
                val streamFile = File.createTempFile("deli-", ".prn", cacheDir).also { cachedStream = it }
                ParcelFileDescriptor.AutoCloseInputStream(source).use { input ->
                    pdfFile.outputStream().use { output ->
                        val buffer = ByteArray(65536)
                        while (true) { checkCancelled(); val size = input.read(buffer); if (size < 0) break; output.write(buffer, 0, size) }
                    }
                }
                val geometry = Geometry.forMedia(info.attributes?.mediaSize?.id)
                val gray = info.attributes?.colorMode == PrintAttributes.COLOR_MODE_MONOCHROME
                fun option(name: String) = info.getAdvancedStringOption(Options.key(name)) ?: Options.choices.getValue(name).first()
                Options.choices.forEach { (key, values) -> require(option(key) in values) { "Invalid $key" } }
                val ranges = info.pages?.takeUnless { pages -> pages.any { it == android.print.PageRange.ALL_PAGES } }
                    ?.joinToString(",") { "${it.start + 1}-${it.end + 1}" }
                PdfRenderer(ParcelFileDescriptor.open(pdfFile, ParcelFileDescriptor.MODE_READ_ONLY)).use { renderer ->
                    val pages = NativeEncoder.plan(renderer.pageCount, ranges, option("duplex"), option("pass2"))
                    if (pages.isNotEmpty()) ParcelFileDescriptor.open(streamFile, ParcelFileDescriptor.MODE_WRITE_ONLY or ParcelFileDescriptor.MODE_TRUNCATE).use { output ->
                        val media = mapOf("Auto" to 0, "Plain" to 0xff, "Matte" to 0xdc, "Heavy" to 0xdd, "Envelope" to 0xf7, "Postcard" to 0xf6).getValue(option("media"))
                        val handle = NativeEncoder.begin(output.fd, geometry.name, media, option("quality").uppercase(java.util.Locale.ROOT), gray, info.copies, info.label.take(200))
                        try {
                            pages.forEachIndexed { index, number ->
                                checkCancelled()
                                main.post { if (!task.cancelled.get()) { job.setStatus("Rendering ${index + 1}/${pages.size}"); job.setProgress(index.toFloat() / pages.size * 0.8f) } }
                                val page = if (number > 0) renderer.openPage(number - 1) else null
                                try {
                                    NativeEncoder.startPage(handle)
                                    var y = 0
                                    while (y < geometry.height) {
                                        checkCancelled()
                                        val rows = min(256, geometry.height - y)
                                        val bitmap = Bitmap.createBitmap(geometry.width, rows, Bitmap.Config.ARGB_8888)
                                        try {
                                            bitmap.eraseColor(Color.WHITE)
                                            if (page != null) page.render(bitmap, null, transform(page.width, page.height, geometry, y), PdfRenderer.Page.RENDER_MODE_FOR_PRINT)
                                            val pixels = IntArray(geometry.width * rows)
                                            bitmap.getPixels(pixels, 0, geometry.width, 0, 0, geometry.width, rows)
                                            NativeEncoder.push(handle, pixels, geometry.width, rows)
                                        } finally { bitmap.recycle() }
                                        y += rows
                                    }
                                    NativeEncoder.endPage(handle)
                                } finally { page?.close() }
                            }
                            NativeEncoder.finish(handle)
                        } finally { NativeEncoder.close(handle) }
                    }
                }
                checkCancelled()
                if (streamFile.length() > 0) {
                    val host = info.printerId?.localId ?: throw IOException("Missing printer")
                    require(Printers(this).list().any { it.host == host }) { "Printer was removed" }
                    val socket = Socket()
                    task.socket.set(socket)
                    val timeout = timer.schedule({ try { socket.close() } catch (_: IOException) {} }, 120, TimeUnit.SECONDS)
                    try {
                        socket.use {
                            checkCancelled(); socket.connect(InetSocketAddress(host, 9100), 8000)
                            main.post { if (!task.cancelled.get()) job.setStatus("Sending to $host:9100") }
                            streamFile.inputStream().use { input ->
                                val output = socket.getOutputStream(); val bytes = ByteArray(65536); var sent = 0L
                                while (true) {
                                    checkCancelled(); val size = input.read(bytes); if (size < 0) break
                                    output.write(bytes, 0, size); sent += size
                                    val progress = 0.8f + 0.2f * sent / streamFile.length()
                                    main.post { if (!task.cancelled.get()) job.setProgress(progress) }
                                }
                                output.flush()
                            }
                        }
                    } finally { timeout.cancel(false); task.socket.set(null) }
                }
                main.post { if (!task.cancelled.get()) job.complete() }
            } catch (e: Exception) {
                main.post { if (!task.cancelled.get()) job.fail(e.message ?: "Print failed") }
            } finally {
                try { source.close() } catch (_: IOException) {}
                cachedPdf?.delete(); cachedStream?.delete(); running.remove(info.id)
            }
        }
    }
    override fun onDestroy() {
        running.values.forEach { it.cancelled.set(true); try { it.socket.get()?.close() } catch (_: IOException) {} }
        worker.shutdown(); timer.shutdown(); super.onDestroy()
    }
}

internal fun transform(width: Int, height: Int, geometry: Geometry, y: Int): Matrix {
    val rotate = (width > height) != (geometry.physicalWidth > geometry.physicalHeight)
    val rw = if (rotate) height else width
    val rh = if (rotate) width else height
    val same = abs(rw - geometry.physicalWidth * 72f / 600) < 1 && abs(rh - geometry.physicalHeight * 72f / 600) < 1
    val scale = if (same) min(geometry.physicalWidth.toFloat() / rw, geometry.physicalHeight.toFloat() / rh) else min(geometry.width.toFloat() / rw, geometry.height.toFloat() / rh)
    val tx = if (same) -geometry.offset.toFloat() else (geometry.width - rw * scale) / 2
    val ty = (if (same) -geometry.offset.toFloat() else (geometry.height - rh * scale) / 2) - y
    return Matrix().apply { setValues(if (rotate) floatArrayOf(0f, -scale, tx + height * scale, scale, 0f, ty, 0f, 0f, 1f) else floatArrayOf(scale, 0f, tx, 0f, scale, ty, 0f, 0f, 1f)) }
}

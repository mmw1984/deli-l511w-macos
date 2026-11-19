package com.deli.print

import android.content.Intent
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PrintTest {
    @Test fun qualityStrips() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = java.io.File.createTempFile("quality", ".pdf", context.cacheDir)
        try {
            val pdf = android.graphics.pdf.PdfDocument()
            try {
                val page = pdf.startPage(android.graphics.pdf.PdfDocument.PageInfo.Builder(72, 72, 1).create())
                val paint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG)
                paint.color = android.graphics.Color.BLUE
                page.canvas.drawRect(2f, 3f, 67f, 15f, paint)
                paint.color = android.graphics.Color.RED; paint.strokeWidth = 0.35f
                page.canvas.drawLine(0f, 0f, 72f, 72f, paint)
                paint.color = android.graphics.Color.BLACK; paint.textSize = 12f
                page.canvas.drawText("Aa", 10f, 45f, paint)
                pdf.finishPage(page)
                file.outputStream().use { pdf.writeTo(it) }
            } finally { pdf.close() }
            android.graphics.pdf.PdfRenderer(android.os.ParcelFileDescriptor.open(file, android.os.ParcelFileDescriptor.MODE_READ_ONLY)).use { renderer ->
                renderer.openPage(0).use { page ->
                    val geometry = Geometry("test", 128, 320, 128, 320, 0)
                    val bitmap = android.graphics.Bitmap.createBitmap(512, 1280, android.graphics.Bitmap.Config.ARGB_8888)
                    try {
                        bitmap.eraseColor(android.graphics.Color.WHITE)
                        page.render(bitmap, null, transform(page.width, page.height, geometry, 0).apply { postScale(4f, 4f) }, android.graphics.pdf.PdfRenderer.Page.RENDER_MODE_FOR_PRINT)
                        val pixels = IntArray(512 * 1280)
                        bitmap.getPixels(pixels, 0, 512, 0, 0, 512, 1280)
                        val expected = NativeEncoder.downsample(pixels, 128, 1280, 4, 0, 320)
                        val tiled = renderBand(page, geometry, 0, 256, true) + renderBand(page, geometry, 256, 64, true)
                        assertArrayEquals(expected, tiled)
                        assertTrue(tiled.any { it != android.graphics.Color.WHITE })
                        assertFalse(tiled.contentEquals(renderBand(page, geometry, 0, 320, false)))
                    } finally { bitmap.recycle() }
                }
            }
            assertArrayEquals(intArrayOf(0xff123456.toInt()), NativeEncoder.downsample(IntArray(16) { 0xff123456.toInt() }, 1, 4, 4, 0, 1))
            try { NativeEncoder.downsample(intArrayOf(), 1, 4, 4, 0, 1); fail("Empty band accepted") } catch (_: java.io.IOException) {}
            try { NativeEncoder.downsample(IntArray(16), 1, 4, 3, 0, 1); fail("Bad scale accepted") } catch (_: java.io.IOException) {}
        } finally { file.delete() }
    }
    @Test fun planner() {
        for (n in 1..7) for (mode in listOf("Odd", "Even")) for (order in listOf("Auto", "Reverse", "Normal")) {
            val expected = (0 until (n + 1) / 2).map { val p = it * 2 + if (mode == "Odd") 1 else 2; if (p > n) 0 else p }.let { if (mode == "Odd" || order != "Normal") it.reversed() else it }
            assertArrayEquals(expected.toIntArray(), NativeEncoder.plan(n, null, mode, order))
        }
        assertTrue(NativeEncoder.plan(3, "9-10", "Off", "Auto").isEmpty())
        try { NativeEncoder.plan(3, "0", "Off", "Auto"); fail("Invalid range accepted") } catch (_: java.io.IOException) {}
    }
    @Test fun systemPrint() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val manager = context.getSystemService(android.print.PrintManager::class.java)
        val before = manager.printJobs.map { it.id }.toSet()
        Printers(context).add("Deli L511W", "10.0.2.2")
        context.startActivity(Intent(context, PrintTestActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        val device = UiDevice.getInstance(instrumentation)
        assertTrue(device.wait(Until.hasObject(By.pkg("com.android.printspooler")), 30000))
        val destination = device.wait(Until.findObject(By.res("com.android.printspooler", "destination_spinner")), 10000)
        assertNotNull(destination); destination.click()
        val all = device.wait(Until.findObject(By.textContains("All printers")), 5000)
        all?.click()
        val printer = device.wait(Until.findObject(By.textContains("Deli L511W (10.0.2.2)")), 20000)
        assertNotNull("Printer not discovered", printer); printer.click()
        val button = device.wait(Until.findObject(By.res("com.android.printspooler", "print_button")), 20000)
        assertNotNull(button); button.click()
        device.wait(Until.findObject(By.text("OK")), 5000)?.click()
        device.waitForIdle()
        val deadline = android.os.SystemClock.elapsedRealtime() + 90000
        while (android.os.SystemClock.elapsedRealtime() < deadline) {
            val jobs = manager.printJobs.filter { it.id !in before }
            assertFalse("Print failed: ${jobs.map { it.info }}", jobs.any { it.isFailed })
            if (jobs.any { it.isCompleted }) return
            android.os.SystemClock.sleep(200)
        }
        fail("Print job did not complete")
    }
    @Test fun errorsAndStorage() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val store = Printers(context)
        store.add("Test", "192.0.2.1")
        assertTrue(Printers(context).list().any { it.host == "192.0.2.1" })
        store.remove("192.0.2.1")
        assertFalse(store.list().any { it.host == "192.0.2.1" })
        try { store.add("Bad", "999.0.0.1"); fail("Invalid IP accepted") } catch (_: IllegalArgumentException) {}
        try { NativeEncoder.begin(-1, "A4", 255, "NORMAL", false, 1, "error"); fail("Invalid fd accepted") } catch (_: java.io.IOException) {}
        val file = java.io.File.createTempFile("jni-error", ".prn", context.cacheDir)
        try {
            android.os.ParcelFileDescriptor.open(file, android.os.ParcelFileDescriptor.MODE_WRITE_ONLY).use { fd ->
                val handle = NativeEncoder.begin(fd.fd, "A4", 255, "NORMAL", true, 1, "error")
                try {
                    NativeEncoder.startPage(handle)
                    try { NativeEncoder.push(handle, intArrayOf(0), 1, 1); fail("Bad band accepted") } catch (_: java.io.IOException) {}
                    try { NativeEncoder.endPage(handle); fail("Incomplete page accepted") } catch (_: java.io.IOException) {}
                } finally { NativeEncoder.close(handle) }
            }
        } finally { file.delete() }
    }
}

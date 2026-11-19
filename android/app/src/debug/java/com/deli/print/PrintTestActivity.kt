package com.deli.print

import android.app.Activity
import android.graphics.Color
import android.graphics.Paint
import android.graphics.pdf.PdfDocument
import android.os.Bundle
import android.os.CancellationSignal
import android.os.ParcelFileDescriptor
import android.print.*

class PrintTestActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        getSystemService(PrintManager::class.java).print("Deli emulator PDF", object : PrintDocumentAdapter() {
            override fun onLayout(old: PrintAttributes?, new: PrintAttributes, signal: CancellationSignal, callback: LayoutResultCallback, extras: Bundle?) {
                if (signal.isCanceled) callback.onLayoutCancelled()
                else callback.onLayoutFinished(PrintDocumentInfo.Builder("deli-test.pdf").setPageCount(3).setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).build(), true)
            }
            override fun onWrite(pages: Array<PageRange>, destination: ParcelFileDescriptor, signal: CancellationSignal, callback: WriteResultCallback) {
                try {
                    val pdf = PdfDocument()
                    try {
                        for (index in 0..2) if (pages.any { index in it.start..it.end }) {
                            if (signal.isCanceled) { callback.onWriteCancelled(); return }
                            val page = pdf.startPage(PdfDocument.PageInfo.Builder(595, 842, index + 1).create())
                            val paint = Paint().apply { color = listOf(Color.RED, Color.BLUE, Color.GREEN)[index] }
                            page.canvas.drawColor(Color.WHITE)
                            page.canvas.drawRect(60f, 60f, 500f, 180f, paint)
                            paint.color = Color.BLACK; paint.textSize = 32f
                            page.canvas.drawText("Deli page ${index + 1}", 60f, 240f, paint)
                            paint.strokeWidth = 0.5f
                            for (line in 0..20) page.canvas.drawLine(60f, 280f + line * 10, 500f, 280f + line * 10, paint)
                            pdf.finishPage(page)
                        }
                        ParcelFileDescriptor.AutoCloseOutputStream(destination).use { pdf.writeTo(it) }
                    } finally { pdf.close() }
                    callback.onWriteFinished(pages)
                } catch (e: Exception) { callback.onWriteFailed(e.message) }
            }
        }, PrintAttributes.Builder().setMediaSize(PrintAttributes.MediaSize.ISO_A4).setColorMode(PrintAttributes.COLOR_MODE_COLOR).build())
    }
}

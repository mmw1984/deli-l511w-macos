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

package com.deli.print

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.ScrollView

class SettingsActivity : Activity() {
    override fun onCreate(state: Bundle?) { super.onCreate(state); showPrinters() }
    private fun showPrinters() {
        val store = Printers(this)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 64, 24, 24) }
        layout.addView(TextView(this).apply { text = "Deli L511W 打印機\n請先加入 IP，再於系統設定啟用列印服務。只支援原始 TCP 9100。" })
        layout.addView(Button(this).apply { text = "啟用列印服務 Enable print service"; setOnClickListener { startActivity(Intent(Settings.ACTION_PRINT_SETTINGS)) } })
        store.list().forEach { printer ->
            layout.addView(Button(this).apply {
                text = "${printer.name} (${printer.host}) — 移除 Remove"
                setOnClickListener { AlertDialog.Builder(this@SettingsActivity).setMessage("移除 ${printer.name}？").setPositiveButton("移除") { _, _ -> store.remove(printer.host); showPrinters() }.setNegativeButton("取消", null).show() }
            })
        }
        layout.addView(Button(this).apply { text = "加入打印機 Add printer"; setOnClickListener { addPrinter() } })
        setContentView(ScrollView(this).apply { addView(layout) })
    }
    private fun addPrinter() {
        val fields = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24) }
        val name = EditText(this).apply { hint = "名稱 Name"; setText("Deli L511W") }
        val host = EditText(this).apply { hint = "IP address"; inputType = android.text.InputType.TYPE_CLASS_PHONE }
        fields.addView(name); fields.addView(host)
        val dialog = AlertDialog.Builder(this).setTitle("加入打印機").setView(fields).setPositiveButton("加入", null).setNegativeButton("取消", null).create()
        dialog.setOnShowListener {
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                try { Printers(this).add(name.text.toString().trim(), host.text.toString().trim()); dialog.dismiss(); showPrinters() }
                catch (e: IllegalArgumentException) { host.error = e.message }
            }
        }
        dialog.show()
    }
}

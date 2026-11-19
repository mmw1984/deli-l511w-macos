package com.deli.print

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.print.PrintJobInfo
import android.printservice.PrintService
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Spinner
import android.widget.TextView
import android.widget.ScrollView

object Options {
    val choices = linkedMapOf(
        "media" to listOf("Auto", "Plain", "Matte", "Heavy", "Envelope", "Postcard"),
        "quality" to listOf("Normal", "High", "Draft"),
        "duplex" to listOf("Off", "Odd", "Even"),
        "pass2" to listOf("Auto", "Reverse", "Normal"),
        "rendering" to listOf("Smooth", "HighQuality", "Crisp")
    )
    fun key(name: String) = "com.deli.print.$name"
}

class AdvancedActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        @Suppress("DEPRECATION")
        val info = intent.getParcelableExtra<PrintJobInfo>(PrintService.EXTRA_PRINT_JOB_INFO) ?: run { finish(); return }
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 64, 24, 24) }
        layout.addView(TextView(this).apply { text = "進階選項 Advanced options\n手動雙面：Odd 印單數頁，翻面後用同一文件選 Even。先試印4及5頁。次序不對可改 Pass-2 order。\n預設 Smooth。高質平滑用4倍超採樣（較慢、實驗性）；Crisp/Smooth 在 Android 使用相同抗鋸齒，不作閾值處理。" })
        val labels = listOf("紙張種類 Media", "品質 Quality", "手動雙面 Manual duplex (Odd=第1步 / Even=第2步)", "第2步次序 Pass-2 order", "文字清晰度 Rendering")
        val selectors = Options.choices.entries.mapIndexed { index, (key, values) ->
            layout.addView(TextView(this).apply { text = labels[index] })
            Spinner(this).apply {
                adapter = ArrayAdapter(this@AdvancedActivity, android.R.layout.simple_spinner_dropdown_item, values.map { if (it == "HighQuality") "高質平滑 HighQuality" else if (it == "Crisp") "Crisp（不建議）" else it })
                setSelection(values.indexOf(info.getAdvancedStringOption(Options.key(key))).coerceAtLeast(0))
                layout.addView(this)
            }
        }
        layout.addView(Button(this).apply {
            text = "套用 Apply"
            setOnClickListener {
                val builder = PrintJobInfo.Builder(info)
                Options.choices.entries.forEachIndexed { index, (key, values) -> builder.putAdvancedOption(Options.key(key), values[selectors[index].selectedItemPosition]) }
                setResult(RESULT_OK, Intent().putExtra(PrintService.EXTRA_PRINT_JOB_INFO, builder.build())); finish()
            }
        })
        setContentView(ScrollView(this).apply { addView(layout) })
    }
}

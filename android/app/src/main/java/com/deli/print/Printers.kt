package com.deli.print

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class Printer(val name: String, val host: String)

class Printers(context: Context) {
    val preferences = context.getSharedPreferences("printers", Context.MODE_PRIVATE)
    fun list(): List<Printer> {
        val items = JSONArray(preferences.getString("items", "[]"))
        return (0 until items.length()).map {
            val item = items.getJSONObject(it)
            Printer(item.getString("name"), item.getString("host"))
        }
    }
    fun add(name: String, host: String) {
        require(host.split('.').let { parts -> parts.size == 4 && parts.all { it.isNotEmpty() && it.all(Char::isDigit) && (it.toIntOrNull() ?: -1) in 0..255 } }) { "請輸入 IPv4 位址，例如 192.168.1.100" }
        require(name.isNotBlank()) { "請輸入名稱" }
        save(list().filter { it.host != host } + Printer(name, host))
    }
    fun remove(host: String) = save(list().filter { it.host != host })
    private fun save(printers: List<Printer>) {
        val array = JSONArray()
        printers.forEach { array.put(JSONObject().put("name", it.name).put("host", it.host)) }
        preferences.edit().putString("items", array.toString()).apply()
    }
}

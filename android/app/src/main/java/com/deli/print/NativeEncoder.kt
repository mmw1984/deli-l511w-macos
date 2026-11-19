package com.deli.print

object NativeEncoder {
    init { System.loadLibrary("deli_android") }
    external fun begin(fd: Int, paper: String, media: Int, quality: String, gray: Boolean, copies: Int, title: String): Long
    external fun startPage(handle: Long)
    external fun push(handle: Long, pixels: IntArray, width: Int, rows: Int)
    external fun endPage(handle: Long)
    external fun finish(handle: Long)
    external fun close(handle: Long)
    external fun plan(total: Int, ranges: String?, duplex: String, pass2: String): IntArray
}

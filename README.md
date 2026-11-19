# Deli 得力 L511W macOS 打印機驅動

Experimental macOS printer driver for the Deli L511W.

## 下載

[下載最新安裝檔 Deli-L511W-universal.pkg](https://github.com/mmw1984/deli-l511w-macos/releases/latest/download/Deli-L511W-universal.pkg)

支援 Apple Silicon 及 Intel Mac（macOS 11 或以上）。新功能仍屬實驗性質，建議先試印幾頁。

## 安裝

下載後按住 Control 點擊安裝檔，選「打開」，跟指示安裝。安裝檔未經 Apple 公證。
亦可在「終端機」執行（只安裝你信任的下載檔）：

```sh
sudo installer -pkg ~/Downloads/Deli-L511W-universal.pkg -target /
```

## 加打印機

先在路由器設定 **DHCP reservation（位址保留）**，固定打印機 IP。

「系統設定 → 打印機與掃描器 → 加入打印機 → IP」：
- 位址：打印機 IP。
- 通訊協定：**HP Jetdirect – Socket**。
- 使用：「選擇軟件」→ **Deli L511W**（不要選 AirPrint）。

更新驅動後請刪除舊打印機，再加一次，確保新選項出現。

## 黑白

macOS 不會顯示獨立的「Black & White／黑白」勾選框。
列印時選「黑白 Black & White」預設組合，或將 **Color Mode／色彩模式** 設為 **Grayscale**；要印彩色就選「彩色 Color」預設組合（視乎 App 是否顯示）。

## 手動雙面

先用有頁碼的4頁及5頁文件測試，每次只印一份。兩次都選同一份完整文件，不要再由 App 篩選奇偶頁。

1. 「手動雙面 Manual Duplex」選 **第1步 單數頁**，等全部印完。
2. 保持整疊紙次序、左右翻面，空白面朝向可列印的一面放回紙匣；再選 **第2步 雙數頁** 列印。
   進紙朝向先用測試頁確認；奇數頁文件會自動補一張空白背面，請保留整疊紙。

若背面配錯頁，將「第2步次序 Pass-2 order」由 **Auto** 改 **Normal** 或 **Reverse** 再試。
若只是背面上下倒轉，請改放紙方向。

## 文字清晰度

「文字清晰度 Rendering」預設及建議用 **Smooth**；**Crisp（不建議）** 可能令邊緣出現鋸齒及雜訊。
此選項只影響直接 PDF 列印，不能修復原本已模糊的掃描圖。

## Android

下載 [Android APK](https://github.com/mmw1984/deli-l511w-macos/releases/latest/download/Deli-L511W-Android.apk) 並安裝。
開啟 **Deli L511W Print** → 加入打印機 IP → 啟用列印服務；之後在 App 的系統列印選單選 Deli L511W。
未有 APK 的版本可參考 [Android 建置說明](android/README.md)。

## 解除安裝

先在「系統設定 → 打印機與掃描器」刪除使用此驅動的打印機，再執行：

```sh
sudo rm -rf /Library/Printers/Deli
sudo rm -f /Library/Printers/PPDs/Contents/Resources/Deli-L511W.ppd
sudo pkgutil --forget org.openprinting.experimental.deli-l511w
```

[技術／建置說明](docs/TECHNICAL.md) · [測試紀錄](docs/CHECKS.md) · [網絡協定分析](docs/LANGUAGE-MONITOR.md)

using System;
using System.IO;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Printing;
using System.Printing.Interop;

class PrintPng {
 [DllImport("winspool.drv",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool OpenPrinter(string n,out IntPtr h,IntPtr d);
 [DllImport("winspool.drv")] static extern bool ClosePrinter(IntPtr h);
 [DllImport("winspool.drv",CharSet=CharSet.Unicode)] static extern int DocumentProperties(IntPtr w,IntPtr h,string n,IntPtr o,IntPtr i,int m);
 [DllImport("winspool.drv",CharSet=CharSet.Unicode)] static extern bool GetPrinter(IntPtr h,int l,IntPtr p,int s,out int needed);
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)] static extern IntPtr CreateDC(string d,string n,string o,IntPtr dm);
 [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr h);
 [DllImport("gdi32.dll")] static extern int GetDeviceCaps(IntPtr h,int n);
 [DllImport("gdi32.dll")] static extern int SetMapMode(IntPtr h,int mode);
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct DOCINFO {public int cbSize; public string lpszDocName,lpszOutput,lpszDatatype; public int fwType;}
 [DllImport("gdi32.dll",CharSet=CharSet.Unicode)] static extern int StartDoc(IntPtr h,ref DOCINFO d);
 [DllImport("gdi32.dll")] static extern int StartPage(IntPtr h);
 [DllImport("gdi32.dll")] static extern int EndPage(IntPtr h);
 [DllImport("gdi32.dll")] static extern int EndDoc(IntPtr h);
 [DllImport("gdi32.dll")] static extern int AbortDoc(IntPtr h);
 [StructLayout(LayoutKind.Sequential)] struct BI {public int size,width,height;public short planes,bpp;public int compression,sizeImage,xppm,yppm,used,important;}
 [DllImport("gdi32.dll")] static extern int StretchDIBits(IntPtr h,int x,int y,int w,int hh,int sx,int sy,int sw,int sh,IntPtr bits,ref BI bi,uint use,uint rop);
 static Dictionary<string,string> a=new Dictionary<string,string>();
 static string Arg(string k,string def){return a.ContainsKey(k)?a[k]:def;}
 static short S(byte[] b,int o){return BitConverter.ToInt16(b,o);} static uint U(byte[] b,int o){return BitConverter.ToUInt32(b,o);}
 static void W(byte[] b,int o,short v){Array.Copy(BitConverter.GetBytes(v),0,b,o,2);} static void WU(byte[] b,int o,uint v){Array.Copy(BitConverter.GetBytes(v),0,b,o,4);}
 static string Hex(byte[] b){return BitConverter.ToString(b).Replace("-","");}
 static void Check(bool ok,string what){if(!ok)throw new Exception(what+" failed (Win32 "+Marshal.GetLastWin32Error()+")");}
 static Dictionary<string,object> Fields(byte[] b){var d=new Dictionary<string,object>(); string[] names={"dmOrientation","dmPaperSize","dmPaperLength","dmPaperWidth","dmScale","dmCopies","dmDefaultSource","dmPrintQuality","dmColor","dmDuplex","dmYResolution","dmTTOption","dmCollate"};for(int i=0;i<names.Length;i++)d[names[i]]=S(b,76+2*i);d["dmFields"]=U(b,72);d["dmMediaType"]=U(b,196);d["dmSize"]=S(b,68);d["dmDriverExtra"]=S(b,70);d["dmSpecVersion"]=S(b,64);d["dmDriverVersion"]=S(b,66);d["dmDeviceName"]=System.Text.Encoding.Unicode.GetString(b,0,64).TrimEnd('\0');d["dmFormName"]=System.Text.Encoding.Unicode.GetString(b,102,64).TrimEnd('\0');d["dmICMMethod"]=U(b,188);d["dmICMIntent"]=U(b,192);d["dmDitherType"]=U(b,200);return d;}
 static void Json(string p,object o){File.WriteAllText(p,new JavaScriptSerializer().Serialize(o));}
 static int Main(string[] args){try{Run(args);return 0;}catch(Exception e){Console.Error.WriteLine(e.ToString());return 1;}}
 static void Run(string[] args){
  for(int i=0;i<args.Length;i+=2){if(!args[i].StartsWith("--")||i+1==args.Length)throw new Exception("Expected --name value pairs");a.Add(args[i].Substring(2),args[i+1]);}
  string printer=Arg("printer","Deli L511W"), output=Arg("output",null),dump=Arg("dump",null);
  if(output==null&&dump==null)throw new Exception("Use --dump path or --output path --images PNG[;PNG] [--paper A4|A5|Letter|LetterCustom] [--color color|mono] [--media LIGHT|MATTE|HEAVY|ENV|POSTCARD] [--devmode blob] [--job name] [--ticket path] [--record path]");
  IntPtr ph;Check(OpenPrinter(printer,out ph,IntPtr.Zero),"OpenPrinter");byte[] b;IntPtr p=IntPtr.Zero;
  try{int size=DocumentProperties(IntPtr.Zero,ph,printer,IntPtr.Zero,IntPtr.Zero,0);Check(size>0,"DocumentProperties size");p=Marshal.AllocHGlobal(size);Check(DocumentProperties(IntPtr.Zero,ph,printer,p,IntPtr.Zero,2)==1,"DocumentProperties default");b=new byte[size];Marshal.Copy(p,b,0,size);
   int need;GetPrinter(ph,9,IntPtr.Zero,0,out need);if(need>0){IntPtr q=Marshal.AllocHGlobal(need);try{if(GetPrinter(ph,9,q,need,out need)){IntPtr dm=Marshal.ReadIntPtr(q);if(dm!=IntPtr.Zero){int len=(ushort)Marshal.ReadInt16(dm,68)+(ushort)Marshal.ReadInt16(dm,70);b=new byte[len];Marshal.Copy(dm,b,0,len);}}}finally{Marshal.FreeHGlobal(q);}}
   if(dump!=null){File.WriteAllBytes(dump,b);Json(dump+".json",Fields(b));File.WriteAllText(dump+".hex.txt",Hex(b));Console.WriteLine("Dumped "+b.Length+" bytes to "+dump);return;}
   if(a.ContainsKey("devmode"))b=File.ReadAllBytes(a["devmode"]);
   Check(b.Length>=220&&(ushort)S(b,68)+(ushort)S(b,70)==b.Length,"DEVMODE blob length");
   string paper=Arg("paper","A4"),color=Arg("color","color"),media=Arg("media","LIGHT");
   var papers=new Dictionary<string,short>{{"A4",9},{"A5",11},{"Letter",1},{"LetterCustom",256}};var medias=new Dictionary<string,uint>{{"LIGHT",259},{"MATTE",260},{"HEAVY",258},{"ENV",257},{"POSTCARD",261}};
   if(!papers.ContainsKey(paper)||!medias.ContainsKey(media)||(color!="color"&&color!="mono"))throw new Exception("Invalid paper/color/media");
   uint flags=U(b,72)|1u|2u|0x400u|0x800u|0x1000u|0x2000u|0x2000000u;flags &=~(4u|8u|0x10000u);
   W(b,76,1);W(b,78,papers[paper]);W(b,90,600);W(b,92,(short)(color=="color"?2:1));W(b,94,1);W(b,96,600);WU(b,196,medias[media]);if(paper=="LetterCustom"){flags|=12;W(b,80,2794);W(b,82,2159);}WU(b,72,flags);
   byte[] requested=(byte[])b.Clone();Marshal.FreeHGlobal(p);p=Marshal.AllocHGlobal(Math.Max(size,b.Length));Marshal.Copy(b,0,p,b.Length);Check(DocumentProperties(IntPtr.Zero,ph,printer,p,p,10)==1,"DocumentProperties validate");int total=(ushort)Marshal.ReadInt16(p,68)+(ushort)Marshal.ReadInt16(p,70);b=new byte[total];Marshal.Copy(p,b,0,total);
   string[] images=Arg("images","").Split(';');foreach(string f in images)Check(File.Exists(f),"Input PNG "+f);
   string ticket=Arg("ticket",output+".ticket.xml");using(var converter=new PrintTicketConverter(printer,1)){PrintTicket t=converter.ConvertDevModeToPrintTicket(b,PrintTicketScope.JobScope);using(var stream=t.GetXmlStream())using(var dest=File.Create(ticket))stream.CopyTo(dest);}
   IntPtr dc=CreateDC("WINSPOOL",printer,null,p);Check(dc!=IntPtr.Zero,"CreateDC");var caps=new Dictionary<string,int>();string[] cn={"PHYSICALOFFSETX","PHYSICALOFFSETY","LOGPIXELSX","LOGPIXELSY","HORZRES","VERTRES","PHYSICALWIDTH","PHYSICALHEIGHT"};int[] ci={112,113,88,90,8,10,110,111};bool active=false;
   try{for(int i=0;i<ci.Length;i++)caps[cn[i]]=GetDeviceCaps(dc,ci[i]);Check(caps["LOGPIXELSX"]==600&&caps["LOGPIXELSY"]==600,"600 DPI device caps");Check(!File.Exists(output),"Output must not already exist");var doc=new DOCINFO{cbSize=Marshal.SizeOf(typeof(DOCINFO)),lpszDocName=Arg("job",Path.GetFileNameWithoutExtension(output)),lpszOutput=Path.GetFullPath(output)};Check(StartDoc(dc,ref doc)>0,"StartDoc");active=true;
    foreach(string f in images){Check(StartPage(dc)>0,"StartPage");Check(SetMapMode(dc,1)!=0,"SetMapMode MM_TEXT");using(var src=new Bitmap(f))using(var bitmap=new Bitmap(src.Width,src.Height,PixelFormat.Format24bppRgb)){using(var g=Graphics.FromImage(bitmap)){g.PageUnit=GraphicsUnit.Pixel;g.Clear(Color.White);g.DrawImage(src,new Rectangle(0,0,src.Width,src.Height),0,0,src.Width,src.Height,GraphicsUnit.Pixel);}var data=bitmap.LockBits(new Rectangle(0,0,bitmap.Width,bitmap.Height),ImageLockMode.ReadOnly,PixelFormat.Format24bppRgb);try{Check(data.Stride>0,"Positive DIB stride");var bi=new BI{size=40,width=bitmap.Width,height=-bitmap.Height,planes=1,bpp=24,sizeImage=data.Stride*bitmap.Height};int r=StretchDIBits(dc,-caps["PHYSICALOFFSETX"],-caps["PHYSICALOFFSETY"],bitmap.Width,bitmap.Height,0,0,bitmap.Width,bitmap.Height,data.Scan0,ref bi,0,0x00CC0020);Check(r!=0&&r!=-1,"StretchDIBits");}finally{bitmap.UnlockBits(data);}}Check(EndPage(dc)>0,"EndPage");}Check(EndDoc(dc)>0,"EndDoc");active=false;
   }finally{if(active)AbortDoc(dc);DeleteDC(dc);}
   DateTime until=DateTime.UtcNow.AddSeconds(90);while((!File.Exists(output)||new FileInfo(output).Length==0)&&DateTime.UtcNow<until)System.Threading.Thread.Sleep(200);Check(File.Exists(output)&&new FileInfo(output).Length>0,"Nonempty output");string hash;using(var sha=SHA256.Create())using(var stream=File.OpenRead(output))hash=Hex(sha.ComputeHash(stream));byte[] extra=new byte[(ushort)S(b,70)];Array.Copy(b,(ushort)S(b,68),extra,0,extra.Length);string blob=Arg("record",output+".json")+".devmode.bin";File.WriteAllBytes(blob,b);
   Json(Arg("record",output+".json"),new {filename=output,sourceImages=images,settings=new {printer,paper,color,media,qualityBlob=Arg("devmode",null),job=Arg("job",Path.GetFileNameWithoutExtension(output))},requestedDevmode=Fields(requested),devmode=Fields(b),driverExtraHex=Hex(extra),devmodeBlob=blob,ticketFile=ticket,devcaps=caps,fileSize=new FileInfo(output).Length,sha256=hash});Console.WriteLine(Path.GetFileName(output)+" "+new FileInfo(output).Length+" bytes "+hash);
  }finally{if(p!=IntPtr.Zero)Marshal.FreeHGlobal(p);ClosePrinter(ph);}
 }
}

from PIL import Image, ImageDraw
W,H=4960,7016
im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
cols=[(255,0,0),(0,255,0),(0,0,255),(0,255,255),(255,0,255),(255,255,0),(0,0,0),(128,128,128)]
for i,c in enumerate(cols): d.rectangle([200+i*560,300,200+i*560+500,1300],fill=c)
for x in range(W):
  v=int(255*x/W); d.line([(x,1600),(x,2600)],fill=(v,v,v))
for y in range(3000,6800,100): d.line([(200,y),(W-200,y)],fill=(0,0,0),width=4)
for x in range(200,W-200,100): d.line([(x,3000),(x,6800)],fill=(0,0,0),width=4)
im.save('a4_color_600.png',dpi=(600,600))
im.convert('L').save('a4_gray_600.png',dpi=(600,600))
s=Image.new('RGB',(W,H),'white');ImageDraw.Draw(s).rectangle([0,0,W-1,255],fill=(255,0,0));s.save('a4_band_600.png',dpi=(600,600))

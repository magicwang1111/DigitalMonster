from PIL import Image, ImageDraw
from pathlib import Path
import math,json
root=Path('digitalmon/static/pet'); sheet=Image.open(root/'evolution-pixel.png').convert('RGBA'); w,h=sheet.size
manifest={}
for stage,name in enumerate(['guilmon','growlmon','wargrowlmon','gallantmon']):
 x,y=stage%2,stage//2
 sprite=sheet.crop((x*w//2,y*h//2,(x+1)*w//2,(y+1)*h//2)); box=sprite.getbbox(); sprite=sprite.crop(box); sprite.thumbnail((200,210),Image.Resampling.NEAREST)
 for action in ['idle','pet','feed','evolve']:
  frames=[]
  for i in range(12):
   phase=math.sin(i/12*math.tau); frame=Image.new('RGBA',(256,256)); draw=ImageDraw.Draw(frame)
   dy=round(2*phase) if action=='idle' else -round(abs(phase)*14)
   frame.alpha_composite(sprite,((256-sprite.width)//2,230-sprite.height+dy))
   if action=='pet':
    px=180; py=40-round(i*2); draw.polygon([(px,py+4),(px-6,py-2),(px-11,py+2),(px-10,py+8),(px,py+17),(px+10,py+8),(px+11,py+2),(px+6,py-2)],fill=(255,120,160,255))
   if action=='feed':
    draw.rectangle((28,184,52,204),fill=(220,159,76,255)); draw.rectangle((32,180,48,185),fill=(255,221,153,255))
   if action=='evolve':
    for k in range(8):
     a=k*math.tau/8+i*.13; px=128+int(105*math.cos(a));py=128+int(105*math.sin(a));draw.rectangle((px,py,px+4,py+4),fill=(255,224,115,255))
   frames.append(frame)
  path=root/f'{name}-{action}.gif'
  frames[0].save(path,save_all=True,append_images=frames[1:],duration=100,loop=0,disposal=2,transparency=0)
  manifest[f'{name}-{action}']={'frames':12,'fps':10,'size':[256,256],'method':'procedural sprite motion and interaction effects'}
(root/'animations.json').write_text(json.dumps(manifest,indent=2))
Image.open(root/'guilmon-idle.gif').save(root/'pet.ico',sizes=[(32,32),(48,48),(256,256)])
print('Exported',len(manifest),'GIF animations')

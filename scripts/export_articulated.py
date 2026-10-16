"""Extract generated articulated poses, preserving a common scale and foot anchor."""
import json
from pathlib import Path
from PIL import Image
from collections import deque

ROOT = Path(__file__).resolve().parents[1]/'digitalmon/static/pet'

def clean_edge_fragments(alpha):
    """Drop disconnected neighbour-frame fragments clipped by a cell boundary."""
    w,h=alpha.size
    mask=bytearray(alpha.tobytes()); seen=bytearray(w*h); components=[]
    for start,value in enumerate(mask):
        if not value or seen[start]:continue
        seen[start]=1; queue=deque([start]); pixels=[]; edge=False
        while queue:
            p=queue.popleft(); pixels.append(p); x,y=p%w,p//w
            edge |= x==0 or x==w-1 or y==0 or y==h-1
            for nx,ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                q=ny*w+nx
                if 0<=nx<w and 0<=ny<h and mask[q] and not seen[q]:
                    seen[q]=1;queue.append(q)
        components.append((pixels,edge))
    largest=max((len(p) for p,e in components),default=0)
    for pixels,edge in components:
        if len(pixels)<8 or edge and len(pixels)<largest*.25:
            for p in pixels:mask[p]=0
    return Image.frombytes('L',(w,h),bytes(mask))

def export(source):
    sheet = Image.open(source).convert('RGBA')
    cols, rows = (4, 3) if source.stem.endswith('-feed') else (2, 2)
    cells = []
    for y in range(rows):
        for x in range(cols):
            cell = sheet.crop((x*sheet.width//cols, y*sheet.height//rows,
                               (x+1)*sheet.width//cols, (y+1)*sheet.height//rows))
            alpha = cell.getchannel('A').point(lambda a:255 if a>=128 else 0)
            alpha = clean_edge_fragments(alpha)
            cell.putalpha(alpha)
            box = alpha.getbbox()
            if not box:
                raise ValueError('empty animation frame')
            cells.append(cell.crop(box))
    scale = min(220/max(c.width for c in cells), 220/max(c.height for c in cells))
    frames=[]
    for cell in cells:
        cell=cell.resize((round(cell.width*scale),round(cell.height*scale)),Image.Resampling.NEAREST)
        frame=Image.new('RGBA',(256,256))
        frame.alpha_composite(cell,((256-cell.width)//2,238-cell.height))
        pal=frame.convert('RGB').quantize(colors=255)
        pal=pal.point(lambda v:v+1)
        pal.putpalette([0,0,0]+pal.getpalette()[:765])
        pal.paste(0,mask=frame.getchannel('A').point(lambda a:255 if a<128 else 0))
        frames.append(pal)
    frames[0].save(ROOT/(source.stem+'.gif'),save_all=True,append_images=frames[1:],
                   duration=180 if rows==3 else 400,loop=0,disposal=2,transparency=0,optimize=False)
    return {'frames':len(frames),'duration_ms':180 if rows==3 else 400,
            'method':'generated articulated mouth, arms, tail/cape poses','source':str(source.relative_to(ROOT))}

if __name__=='__main__':
    manifest=json.loads((ROOT/'animations.json').read_text())
    for source in (ROOT/'sources').glob('*.png'):
        manifest[source.stem]=export(source)
    (ROOT/'animations.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')

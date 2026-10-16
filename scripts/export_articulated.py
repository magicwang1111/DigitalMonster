"""Extract generated articulated poses, preserving a common scale and foot anchor."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]/'digitalmon/static/pet'

def export(source):
    sheet = Image.open(source).convert('RGBA')
    cols, rows = (4, 3) if source.stem.endswith('-feed') else (2, 2)
    cells = []
    for y in range(rows):
        for x in range(cols):
            cell = sheet.crop((x*sheet.width//cols, y*sheet.height//rows,
                               (x+1)*sheet.width//cols, (y+1)*sheet.height//rows))
            alpha = cell.getchannel('A').point(lambda a:255 if a>=128 else 0)
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

# SPDX-License-Identifier: GPL-3.0-or-later
"""Native UI catalog and local BLF adapter; no global Blender API patching."""
import bpy, blf as _blf, json, pathlib, os, re
from bpy.app.handlers import persistent
CATALOG=json.loads(pathlib.Path(__file__).with_name('zh_CN.json').read_text(encoding='utf-8'))
_phrases=re.compile(r'(?<![A-Za-z])(?:'+'|'.join(re.escape(k) for k in sorted(CATALOG,key=len,reverse=True))+r')(?![A-Za-z])')
_font_id=None
_font_path=None
def chinese():
    view=bpy.context.preferences.view
    return view.use_translate_interface and bpy.app.translations.locale.lower().startswith('zh')
def tr(text):
    if not isinstance(text,str) or not chinese():return text
    if text in CATALOG:return CATALOG[text]
    if text.endswith(':') and text[:-1] in CATALOG:return CATALOG[text[:-1]]+'：'
    native=bpy.app.translations.pgettext_iface(text)
    if native!=text:return native
    # Compose labels such as 'Translate Z' without partially translating prose.
    remaining=_phrases.sub('',text)
    if not re.search('[A-Za-z]{2,}',remaining):
        return _phrases.sub(lambda m:CATALOG[m.group(0)],text)
    return text
def display_text(text):
    text=str(text)
    # Data-block names are user data, not interface labels.
    if any(text in collection for collection in (bpy.data.objects,bpy.data.materials,bpy.data.collections)):
        return text
    return tr(text)
def font_id(original):
    global _font_id,_font_path
    if not chinese():return original
    if _font_id is None:
        candidates=[pathlib.Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'msyh.ttc',
                    pathlib.Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
        _font_path=next((str(p) for p in candidates if p.is_file()),None)
        _font_id=_blf.load(_font_path) if _font_path else 0
    return _font_id
class LocalBLF:
    def __getattr__(self,name):
        original=getattr(_blf,name)
        if name in {'draw','dimensions'}:
            return lambda fid,text,*a,**kw:original(font_id(fid),display_text(text),*a,**kw)
        if name in {'size','position','color','enable','disable','clipping','rotation','aspect',
                    'shadow','shadow_offset','word_wrap','wrap_width'}:
            return lambda fid,*a,**kw:original(font_id(fid),*a,**kw)
        return original
blf=LocalBLF()
@persistent
def clear_font(_):
    global _font_id,_font_path
    _font_id=None
    _font_path=None
def register():
    entries={(context,en):zh for en,zh in CATALOG.items() for context in ('*','Operator')}
    bpy.app.translations.register(__package__,{'zh_HANS':entries,'zh_CN':entries})
    if clear_font not in bpy.app.handlers.load_post:bpy.app.handlers.load_post.append(clear_font)
def unregister():
    global _font_id,_font_path
    bpy.app.translations.unregister(__package__)
    if clear_font in bpy.app.handlers.load_post:bpy.app.handlers.load_post.remove(clear_font)
    if _font_path:
        try:_blf.unload(_font_path)
        except (ValueError,RuntimeError):pass
    _font_id=None
    _font_path=None

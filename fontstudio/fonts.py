"""Installed monospace faces; CoreText on macOS, Fontconfig on Linux."""
import ctypes as C
from dataclasses import dataclass
import sys
from .core import StudioError, run


@dataclass(frozen=True)
class Font:
    family: str
    name: str
    style: str = "Regular"

    @property
    def label(self):
        return f"{self.family} / {self.style}"


def installed():
    fonts = mac_fonts() if sys.platform == "darwin" else linux_fonts()
    fonts = sorted(set(fonts), key=lambda f: (f.family.casefold(), f.style.casefold(), f.name))
    if not fonts:
        raise StudioError("No monospace fonts found. Linux requires fontconfig (fc-list).")
    return fonts


def linux_fonts():
    output = run(["fc-list", "--format", "%{family[0]}\t%{postscriptname}\t%{style[0]}\n", ":spacing=100"])
    fonts = []
    for row in output.splitlines():
        parts = row.split("\t")
        if len(parts) == 3:
            family, name, style = parts
            fonts.append(Font(family, name or family, style))
    return fonts


def mac_fonts():
    cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = C.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    ptr = C.c_void_p
    def bind(lib, name, result, args):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, args
        return fn
    release = bind(cf, "CFRelease", None, [ptr])
    count = bind(cf, "CFArrayGetCount", C.c_long, [ptr])
    item = bind(cf, "CFArrayGetValueAtIndex", ptr, [ptr, C.c_long])
    length = bind(cf, "CFStringGetLength", C.c_long, [ptr])
    getstr = bind(cf, "CFStringGetCString", C.c_bool, [ptr, ptr, C.c_long, C.c_uint32])
    collection = bind(ct, "CTFontCollectionCreateFromAvailableFonts", ptr, [ptr])(None)
    descriptors = bind(ct, "CTFontCollectionCreateMatchingFontDescriptors", ptr, [ptr])(collection)
    makefont = bind(ct, "CTFontCreateWithFontDescriptor", ptr, [ptr, C.c_double, ptr])
    traits = bind(ct, "CTFontGetSymbolicTraits", C.c_uint32, [ptr])
    copies = [bind(ct, name, ptr, [ptr]) for name in (
        "CTFontCopyFamilyName", "CTFontCopyPostScriptName")]
    copyname = bind(ct, "CTFontCopyName", ptr, [ptr, ptr])
    stylekey = ptr.in_dll(ct, "kCTFontStyleNameKey")
    def string(ref):
        try:
            buf = C.create_string_buffer(length(ref) * 4 + 1)
            if not getstr(ref, buf, len(buf), 0x08000100):
                raise StudioError("Cannot decode font name")
            return buf.value.decode("utf-8")
        finally:
            release(ref)
    fonts = []
    try:
        if not descriptors:
            return []
        for i in range(count(descriptors)):
            font = makefont(item(descriptors, i), 12, None)
            if not font:
                continue
            try:
                if traits(font) & (1 << 10):  # kCTFontMonoSpaceTrait
                    family, name = [string(copy(font)) for copy in copies]
                    style = string(copyname(font, stylekey))
                    fonts.append(Font(family, name, style or "Regular"))
            finally:
                release(font)
    finally:
        if descriptors:
            release(descriptors)
        release(collection)
    return fonts

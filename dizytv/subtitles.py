"""Safe subtitle preferences and libVLC 3.0 track/renderer helpers.

Subtitle styling is configured at VLC instance creation, not per-media:
changing appearance takes effect with the next *new player* instance.
This avoids restarting active live playback or disrupting recordings.
"""
from __future__ import annotations
from pathlib import Path
import re

COLOURS = {
    'White': '0xFFFFFF',
    'Yellow': '0xFFFF00',
    'Cyan': '0x00FFFF',
    'Green': '0x80FF9A',
    'Black': '0x000000',
}
POSITIONS = {'Bottom': 16, 'Raised': 70, 'High': 135}
FONTS = ('Sans', 'Serif', 'Monospace')


def validate_caption_settings(settings):
    if type(settings.get('subtitles_enabled',True)) is not bool:
        raise ValueError('Invalid subtitles enabled flag')
    size=settings.get('subtitle_size',28)
    if type(size) is not int or not 12<=size<=64:
        raise ValueError('Invalid subtitle text size')
    if settings.get('subtitle_colour','White') not in COLOURS:
        raise ValueError('Invalid subtitle colour')
    if settings.get('subtitle_position','Bottom') not in POSITIONS:
        raise ValueError('Invalid subtitle position')
    if settings.get('subtitle_font','Sans') not in FONTS:
        raise ValueError('Invalid subtitle font')
    if settings.get('subtitle_language','Auto') not in ('Auto','English'):
        raise ValueError('Invalid subtitle language preference')
    return settings


def vlc_subtitle_options(settings):
    """Bounded VLC text-renderer options. Bitmap/DVB captions may ignore style."""
    validate_caption_settings(settings)
    font={'Sans':'Arial','Serif':'Georgia','Monospace':'Consolas'}[settings.get('subtitle_font','Sans')]
    return (
        '--freetype-font='+font,
        '--freetype-fontsize='+str(settings.get('subtitle_size',28)),
        '--freetype-color='+COLOURS[settings.get('subtitle_colour','White')],
        '--sub-margin='+str(POSITIONS[settings.get('subtitle_position','Bottom')]),
    )


def subtitle_tracks(player):
    """Get VLC (id, label) descriptions without assuming captions exist."""
    if player is None:return []
    try:
        described=player.video_get_spu_description() or ()
    except (AttributeError,RuntimeError,OSError):
        return []
    result=[];seen=set()
    for item in described:
        if isinstance(item,(tuple,list)) and len(item)>=2:
            identifier,label=item[0],item[1]
        else:
            identifier,label=getattr(item,'id',None),getattr(item,'name',None)
        try:identifier=int(identifier)
        except (TypeError,ValueError):continue
        if identifier<0 or identifier in seen:continue
        seen.add(identifier)
        if isinstance(label,bytes):label=label.decode('utf-8','replace')
        result.append((identifier,str(label or 'Subtitles')))
    return result


def suggested_subtitle(tracks,language='Auto'):
    if not tracks:return None
    if language=='English':
        for identifier,name in tracks:
            label=name.casefold()
            if ('english' in label or re.search(
                    r'(?<![a-z])(?:eng|en)(?:[-_](?:us|gb|uk|au|ca|nz))?(?![a-z])',
                    label)):
                return identifier
    return tracks[0][0]


def external_subtitle_path(path):
    file=Path(path)
    if file.suffix.lower() not in ('.srt','.ass','.ssa','.vtt','.sub'):
        raise ValueError('Choose an SRT, ASS, SSA, VTT or SUB subtitle file')
    if not file.is_file() or file.stat().st_size>10*1024*1024:
        raise ValueError('Subtitle file not found or exceeds 10 MiB')
    return str(file.resolve())

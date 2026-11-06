"""GStreamer pipelines. No shell invocation; filenames are separate arguments."""
import subprocess
from PIL import Image, ImageChops, ImageStat

def recording_crop(source_width,source_height,rect):
    """Convert a selected rectangle to even-sized GStreamer crop margins."""
    left,top,width,height=rect
    left=max(0,min(int(left),source_width-1));top=max(0,min(int(top),source_height-1))
    width=min(int(width),source_width-left)//2*2
    height=min(int(height),source_height-top)//2*2
    if width<2 or height<2:
        raise ValueError('The recording area must be at least 2 × 2 pixels.')
    return left,top,source_width-left-width,source_height-top-height

def gst_string(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'

def audio_source(mode):
    args = ['pulsesrc', 'do-timestamp=true']
    if mode == 'System audio':
        sink = subprocess.check_output(['pactl', 'get-default-sink'], text=True, timeout=5).strip()
        args += ['device=' + gst_string(sink + '.monitor')]
    return args + ['!', 'queue', '!', 'audioconvert', '!', 'audioresample']

def pipeline(output, mode, fd=None, node=None, crop=None, audio='None', fps=30):
    cmd = ['gst-launch-1.0', '-e']
    if mode == 'MP3 audio':
        if audio == 'None':
            raise ValueError('Select microphone or system audio for MP3.')
        return cmd + audio_source(audio) + ['!', 'lamemp3enc', 'target=bitrate',
            'bitrate=192', '!', 'id3v2mux', '!', 'filesink', 'location=' + gst_string(output)]
    cmd += ['pipewiresrc', f'fd={fd}', f'path={node}', 'do-timestamp=true',
            '!', 'queue', '!', 'videoconvert']
    if crop:
        left, top, right, bottom = crop
        cmd += ['!', 'videocrop', f'left={left}', f'top={top}', f'right={right}', f'bottom={bottom}']
    cmd += ['!', 'videorate', '!', f'video/x-raw,framerate={fps}/1',
            '!', 'videoscale', '!', 'video/x-raw,format=I420', '!', 'x264enc',
            'tune=zerolatency', 'speed-preset=veryfast', '!', 'h264parse',
            '!', 'queue', '!', 'mux.', 'mp4mux', 'name=mux', '!',
            'filesink', 'location=' + gst_string(output)]
    if audio != 'None':
        cmd += audio_source(audio) + ['!', 'avenc_aac', '!', 'aacparse', '!', 'queue', '!', 'mux.']
    return cmd

def stitch(images, overlap, top=0, bottom=0):
    if len(images) < 2:
        raise ValueError('Add at least two sections.')
    frames = []
    for im in images:
        if im.height <= top + bottom:
            raise ValueError('Header/footer trim exceeds the image height.')
        frames.append(im.convert('RGB').crop((0, top, im.width, im.height-bottom)))
    if len({x.width for x in frames}) != 1:
        raise ValueError('Sections must have the same width. Use the same capture area.')
    if not 0 <= overlap < min(x.height for x in frames):
        raise ValueError('Overlap must be smaller than every trimmed section.')
    height = sum(x.height for x in frames) - overlap*(len(frames)-1)
    if frames[0].width * height > 100_000_000:
        raise ValueError('Combined image exceeds 100 megapixels. Use fewer sections.')
    out = Image.new('RGB', (frames[0].width, height), 'white')
    y = 0
    for i, im in enumerate(frames):
        if i:
            im = im.crop((0, overlap, im.width, im.height))
        out.paste(im, (0,y))
        y += im.height
    return out

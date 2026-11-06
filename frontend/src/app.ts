import {Component,Input,inject,signal,ViewChild,ElementRef,AfterViewInit,HostListener} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {DomSanitizer} from '@angular/platform-browser';
import {ICONS} from './icons';

@Component({selector:'sf-icon',standalone:true,template:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" [innerHTML]="markup"></svg>'})
export class IconComponent {
  @Input() name='capture';
  private sanitizer=inject(DomSanitizer);
  get markup(){return this.sanitizer.bypassSecurityTrustHtml(ICONS[this.name]||ICONS['image']);}
}

type Point={x:number,y:number};
type Recent={name:string,kind:string,modified:string};
interface Bridge {
  imageReady:{connect:(callback:(data:string)=>void)=>void};
  stateChanged:{connect:(callback:(data:string)=>void)=>void};
  capture:(workflow:string,delay:number)=>void;
  scrolling:()=>void;
  paste:()=>void;
  saveImage:(data:string,format:string,callback:(saved:boolean)=>void)=>void;
  copyImage:(data:string)=>void;
  pinImage:(data:string)=>void;
  recognizeText:(data:string)=>void;
  record:(config:string)=>void;
  stop:()=>void;
  listRecent:(callback:(data:string)=>void)=>void;
  openRecent:(name:string)=>void;
  openFolder:()=>void;
  manual:()=>void;
  syncImage:(data:string)=>void;
}
declare global {interface Window {qt?:{webChannelTransport:unknown};QWebChannel?:new(transport:unknown,callback:(channel:{objects:{bridge:Bridge}})=>void)=>unknown;}}

@Component({selector:'snagforge-app',standalone:true,imports:[CommonModule,FormsModule,IconComponent],templateUrl:'./app.html'})
export class AppComponent implements AfterViewInit {
  @ViewChild('canvas') canvasRef!:ElementRef<HTMLCanvasElement>;
  @ViewChild('fileInput') fileInput!:ElementRef<HTMLInputElement>;
  page=signal('editor');tool=signal('Arrow');color=signal('#7764f2');stroke=signal(5);
  connected=signal(false);hasImage=signal(false);imageName=signal('Untitled capture');dirty=signal(false);
  width=signal(0);height=signal(0);notice=signal('');recording=signal(false);busy=signal(false);elapsed=signal('00:00');
  mode=signal('MP4 video');audio=signal('Microphone');region=signal(true);delay=signal(0);format=signal('png');
  workflow=signal(localStorage.getItem('snagforge.workflow')||'editor');recent=signal<Recent[]>([]);query=signal('');
  tools=['Arrow','Pen','Rectangle','Ellipse','Line','Text','Step','Highlight','Pixelate','Redact','Spotlight','Crop'];
  colors=['#7764f2','#ff795e','#38b693','#f3b845','#24334b'];history:string[]=[];future:string[]=[];
  historySize=signal(0);futureSize=signal(0);zoom=signal(100);demo=signal(false);textOpen=signal(false);textValue='';resizeOpen=signal(false);resizeValue=1200;
  bridge?:Bridge;drawing=false;points:Point[]=[];backup?:ImageData;before='';step=1;timer?:ReturnType<typeof setTimeout>;
  get canvas(){return this.canvasRef.nativeElement;}
  get context(){return this.canvas.getContext('2d',{willReadFrequently:true})!;}
  ngAfterViewInit(){
    if(window.qt&&window.QWebChannel){
      new window.QWebChannel(window.qt.webChannelTransport,channel=>{
        this.bridge=channel.objects.bridge;this.connected.set(true);
        this.bridge.imageReady.connect(data=>{this.page.set('editor');this.demo.set(false);this.load(data,'New capture',true);});
        this.bridge.stateChanged.connect(data=>{const s=JSON.parse(data);const wasBusy=this.busy();this.busy.set(s.busy);this.recording.set(s.recording);this.elapsed.set(s.elapsed||'00:00');if(s.message)this.toast(s.message);if(s.message||(wasBusy&&!s.busy))this.refresh();});
        this.refresh();
      });
    }
  }
  toast(message:string){this.notice.set(message);if(this.timer)clearTimeout(this.timer);this.timer=setTimeout(()=>this.notice.set(''),4200);}
  refresh(){this.bridge?.listRecent(data=>this.recent.set(JSON.parse(data)));}
  capture(){if(this.busy())return;if(!this.bridge){this.toast('Screen capture is available in the SnagForge desktop application.');return;}this.bridge.capture(this.workflow(),this.delay());}
  scrolling(){if(this.busy())return;if(this.bridge)this.bridge.scrolling();else this.toast('Guided scrolling capture is available in the desktop app.');}
  chooseFile(){this.fileInput.nativeElement.click();}
  fileSelected(event:Event){const file=(event.target as HTMLInputElement).files?.[0];if(file)this.readFile(file);(event.target as HTMLInputElement).value='';}
  drop(event:DragEvent){event.preventDefault();const file=event.dataTransfer?.files[0];if(file)this.readFile(file);}
  readFile(file:File){
    if(!/^image\/(png|jpeg|webp|bmp)$/.test(file.type)){this.toast('Choose a PNG, JPEG, WebP or BMP image.');return;}
    if(file.size>50*1024*1024){this.toast('Choose an image smaller than 50 MB.');return;}
    if(this.dirty()&&!window.confirm('Replace the current image? Export it first to keep your changes.'))return;
    const reader=new FileReader();reader.onload=()=>{this.page.set('editor');this.demo.set(false);this.load(String(reader.result),file.name,true);};reader.readAsDataURL(file);
  }
  load(data:string,name?:string,reset=false){
    const image=new Image();image.onload=()=>{
      if(image.width*image.height>100_000_000){this.toast('Images are limited to 100 megapixels.');return;}
      this.canvas.width=image.width;this.canvas.height=image.height;this.context.drawImage(image,0,0);
      this.width.set(image.width);this.height.set(image.height);this.hasImage.set(true);this.dirty.set(true);if(name)this.imageName.set(name);
      if(reset){this.history=[];this.future=[];this.step=1;this.zoom.set(100);this.updateHistory();}
      this.sync();
    };image.onerror=()=>this.toast('This image could not be opened.');image.src=data;
  }
  sync(){if(this.hasImage())this.bridge?.syncImage(this.canvas.toDataURL('image/png'));}
  updateHistory(){this.historySize.set(this.history.length);this.futureSize.set(this.future.length);}
  checkpoint(data:string){this.history.push(data);if(this.history.length>20)this.history.shift();this.future=[];this.dirty.set(true);this.updateHistory();this.sync();}
  undo(){if(!this.history.length)return;this.future.push(this.canvas.toDataURL());this.load(this.history.pop()!);this.updateHistory();}
  redo(){if(!this.future.length)return;this.history.push(this.canvas.toDataURL());this.load(this.future.pop()!);this.updateHistory();}
  point(event:PointerEvent):Point {const rect=this.canvas.getBoundingClientRect();return {x:Math.max(0,Math.min(this.canvas.width,(event.clientX-rect.left)*this.canvas.width/rect.width)),y:Math.max(0,Math.min(this.canvas.height,(event.clientY-rect.top)*this.canvas.height/rect.height))};}
  pointerDown(event:PointerEvent){
    if(!this.hasImage()||event.button!==0)return;event.preventDefault();this.canvas.setPointerCapture(event.pointerId);
    this.points=[this.point(event)];this.before=this.canvas.toDataURL();
    if(this.tool()==='Text'){this.textValue='';this.textOpen.set(true);return;}
    this.backup=this.context.getImageData(0,0,this.canvas.width,this.canvas.height);this.drawing=true;
  }
  pointerMove(event:PointerEvent){if(!this.drawing)return;this.points.push(this.point(event));this.context.putImageData(this.backup!,0,0);this.paint();}
  pointerUp(event:PointerEvent){
    if(!this.drawing)return;this.points.push(this.point(event));this.context.putImageData(this.backup!,0,0);this.paint();this.drawing=false;
    if(this.tool()==='Crop'){
      this.context.putImageData(this.backup!,0,0);const r=this.rectangle();if(r.w<2||r.h<2)return;
      const clipped=this.context.getImageData(r.x,r.y,r.w,r.h);this.canvas.width=clipped.width;this.canvas.height=clipped.height;this.context.putImageData(clipped,0,0);this.width.set(clipped.width);this.height.set(clipped.height);
    }
    if(this.tool()==='Step')this.step++;this.checkpoint(this.before);
  }
  cancelStroke(){if(this.drawing&&this.backup){this.context.putImageData(this.backup,0,0);this.drawing=false;}}
  rectangle(){const a=this.points[0],b=this.points.at(-1)!;return {x:Math.round(Math.min(a.x,b.x)),y:Math.round(Math.min(a.y,b.y)),w:Math.round(Math.abs(a.x-b.x)),h:Math.round(Math.abs(a.y-b.y))};}
  paint(){
    const c=this.context,a=this.points[0],b=this.points.at(-1)!,r=this.rectangle(),t=this.tool();
    c.save();c.strokeStyle=this.color();c.fillStyle=this.color();c.lineWidth=this.stroke();c.lineCap='round';c.lineJoin='round';
    if(t==='Pen'){c.beginPath();c.moveTo(a.x,a.y);for(const p of this.points)c.lineTo(p.x,p.y);c.stroke();}
    else if(t==='Arrow'||t==='Line'){c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();if(t==='Arrow'){const angle=Math.atan2(b.y-a.y,b.x-a.x),size=Math.max(15,this.stroke()*4);c.beginPath();c.moveTo(b.x,b.y);c.lineTo(b.x-size*Math.cos(angle-.5),b.y-size*Math.sin(angle-.5));c.lineTo(b.x-size*Math.cos(angle+.5),b.y-size*Math.sin(angle+.5));c.closePath();c.fill();}}
    else if(t==='Rectangle')c.strokeRect(r.x,r.y,r.w,r.h);
    else if(t==='Ellipse'){c.beginPath();c.ellipse(r.x+r.w/2,r.y+r.h/2,r.w/2,r.h/2,0,0,Math.PI*2);c.stroke();}
    else if(t==='Highlight'){c.globalAlpha=.32;c.fillStyle='#ffce45';c.fillRect(r.x,r.y,r.w,r.h);}
    else if(t==='Step'){const radius=Math.max(18,this.stroke()*4);c.beginPath();c.arc(a.x,a.y,radius,0,Math.PI*2);c.fill();c.fillStyle='#fff';c.font='bold '+radius+'px sans-serif';c.textAlign='center';c.textBaseline='middle';c.fillText(String(this.step),a.x,a.y);}
    else if(t==='Redact'){c.fillStyle='#111827';c.fillRect(r.x,r.y,r.w,r.h);}
    else if(t==='Spotlight'&&r.w&&r.h){const part=c.getImageData(r.x,r.y,r.w,r.h);c.fillStyle='rgba(7,15,30,.62)';c.fillRect(0,0,this.canvas.width,this.canvas.height);c.putImageData(part,r.x,r.y);}
    else if(t==='Pixelate'&&r.w&&r.h){const small=document.createElement('canvas');small.width=Math.max(1,Math.ceil(r.w/14));small.height=Math.max(1,Math.ceil(r.h/14));small.getContext('2d')!.drawImage(this.canvas,r.x,r.y,r.w,r.h,0,0,small.width,small.height);c.imageSmoothingEnabled=false;c.drawImage(small,0,0,small.width,small.height,r.x,r.y,r.w,r.h);}
    else if(t==='Crop'){c.setLineDash([8,5]);c.strokeStyle='#7764f2';c.strokeRect(r.x,r.y,r.w,r.h);}
    c.restore();
  }
  applyText(){if(this.textValue.trim()){const c=this.context;c.fillStyle=this.color();c.font=Math.max(20,this.stroke()*5)+'px sans-serif';this.textValue.split('\n').forEach((line,i)=>c.fillText(line,this.points[0].x,this.points[0].y+i*Math.max(25,this.stroke()*6)));this.checkpoint(this.before);}this.textOpen.set(false);}
  rotate(){if(!this.hasImage())return;const before=this.canvas.toDataURL(),copy=document.createElement('canvas');copy.width=this.canvas.height;copy.height=this.canvas.width;const c=copy.getContext('2d')!;c.translate(copy.width,0);c.rotate(Math.PI/2);c.drawImage(this.canvas,0,0);this.load(copy.toDataURL());this.checkpoint(before);}
  resize(){if(!this.hasImage())return;this.resizeValue=this.width();this.resizeOpen.set(true);}
  applyResize(){const width=Math.floor(this.resizeValue),height=Math.round(width*this.height()/this.width());if(width<1||height<1||width*height>100_000_000){this.toast('Choose a valid size below 100 megapixels.');return;}const before=this.canvas.toDataURL(),copy=document.createElement('canvas');copy.width=width;copy.height=height;copy.getContext('2d')!.drawImage(this.canvas,0,0,width,height);this.load(copy.toDataURL());this.checkpoint(before);this.resizeOpen.set(false);}
  exportImage(){
    if(!this.hasImage())return;const mime='image/'+(this.format()==='jpg'?'jpeg':this.format());const data=this.canvas.toDataURL(mime,.95);
    if(this.bridge){this.bridge.saveImage(data,this.format(),saved=>{if(saved)this.dirty.set(false);});return;}else{const link=document.createElement('a');link.download='snagforge-capture.'+this.format();link.href=data;link.click();this.toast('Image exported.');}this.dirty.set(false);
  }
  copy(){if(!this.hasImage())return;if(this.bridge){this.bridge.copyImage(this.canvas.toDataURL());this.toast('Image copied to clipboard.');}else this.toast('Clipboard integration is available in the desktop app.');}
  paste(){if(this.bridge)this.bridge.paste();else this.toast('Use Open image or drop an image into this workspace.');}
  pin(){if(!this.hasImage())return;if(this.bridge)this.bridge.pinImage(this.canvas.toDataURL());else this.toast('Pinned reference windows are available in the desktop app.');}
  ocr(){if(!this.hasImage())return;if(this.bridge)this.bridge.recognizeText(this.canvas.toDataURL());else this.toast('Local OCR is available in the desktop app.');}
  record(){if(!this.bridge){this.toast('Launch the desktop application for real screen and audio recording.');return;}this.bridge.record(JSON.stringify({mode:this.mode(),audio:this.audio(),region:this.region(),delay:this.delay()}));}
  stop(){this.bridge?.stop();}
  setWorkflow(value:string){this.workflow.set(value);localStorage.setItem('snagforge.workflow',value);}
  filteredRecent(){const q=this.query().toLowerCase();return this.recent().filter(r=>r.name.toLowerCase().includes(q));}
  openRecent(item:Recent){this.bridge?.openRecent(item.name);}
  folder(){if(this.bridge)this.bridge.openFolder();else this.toast('The desktop app saves to Pictures/SnagForge.');}
  manual(){if(this.bridge)this.bridge.manual();else this.toast('The illustrated manual is included in the repository under docs/.');}
  demoImage(){
    if(this.dirty()&&!window.confirm('Replace the current image with the example?'))return;
    this.page.set('editor');this.demo.set(true);const sample=document.createElement('canvas');sample.width=1200;sample.height=760;const c=sample.getContext('2d')!;
    c.fillStyle='#f5f7fb';c.fillRect(0,0,1200,760);c.fillStyle='#fff';c.fillRect(0,0,1200,82);c.fillStyle='#7966ec';c.fillRect(30,26,30,30);c.fillStyle='#1f2c44';c.font='bold 21px sans-serif';c.fillText('Orbit',73,48);c.fillStyle='#9ba5b5';c.font='14px sans-serif';c.fillText('Workspace  /  Projects  /  Overview',260,48);c.fillText('Demo workspace',1015,48);
    c.fillStyle='#1d2941';c.font='bold 33px sans-serif';c.fillText('Project overview',46,150);c.fillStyle='#94a0b3';c.font='16px sans-serif';c.fillText('Everything your team needs, in one place.',46,181);
    for(const [i,title,value,detail] of [[0,'ACTIVE PROJECTS','12','Across 3 workspaces'],[1,'TASKS COMPLETE','84%','Up 12% this month'],[2,'OPEN REVIEWS','03','Ready for feedback']] as const){const x=46+i*374;c.fillStyle='#fff';c.beginPath();c.roundRect(x,215,350,142,12);c.fill();c.fillStyle='#9aa5b8';c.font='12px sans-serif';c.fillText(title,x+24,249);c.fillStyle='#26354e';c.font='bold 40px sans-serif';c.fillText(value,x+24,302);c.fillStyle=i===1?'#38ab8e':'#a9b3c2';c.font='12px sans-serif';c.fillText(detail,x+24,331);}
    c.fillStyle='#fff';c.beginPath();c.roundRect(46,382,1100,310,12);c.fill();c.fillStyle='#26354e';c.font='bold 19px sans-serif';c.fillText('Release readiness',72,422);
    const rows=[['Screenshot editor','Ready for review'],['Screen recording','Desktop validation pending'],['Documentation','Draft complete']];rows.forEach((row,i)=>{const y=465+i*70;c.fillStyle='#edf0f6';c.fillRect(72,y+31,1048,1);c.fillStyle='#596981';c.font='16px sans-serif';c.fillText(row[0],72,y);c.fillStyle='#6a59d9';c.font='13px sans-serif';c.fillText(row[1],830,y);});
    c.fillStyle='#a1aabe';c.font='12px sans-serif';c.fillText('Synthetic demonstration content · No personal information',46,730);
    this.load(sample.toDataURL(),'Project overview · Example',true);
  }
  @HostListener('window:keydown',['$event']) keyboard(event:KeyboardEvent){
    const target=event.target as HTMLElement;if(['INPUT','TEXTAREA','SELECT'].includes(target.tagName))return;
    if(event.key==='Escape'){this.cancelStroke();this.textOpen.set(false);return;}
    if(event.ctrlKey||event.metaKey){const key=event.key.toLowerCase();if(['z','s','o','c','v','n'].includes(key))event.preventDefault();if(key==='z')event.shiftKey?this.redo():this.undo();if(key==='s')this.exportImage();if(key==='o')this.chooseFile();if(key==='c')this.copy();if(key==='v')this.paste();if(key==='n')this.capture();}
  }
}

const captureButton=document.querySelector('#capture'), exerciseSelect=document.querySelector('#capture-exercise'), captureStatus=document.querySelector('#capture-status');
let capturing=false, captureController=null, reviewUrls=[];
function clearCapture(){reviewUrls.forEach(url=>URL.revokeObjectURL(url));reviewUrls=[];document.querySelector('#reviews').replaceChildren();document.querySelector('#feature-json').textContent='';document.querySelector('#feature-details').hidden=true}
function syncCapture(){captureButton.disabled=!active||capturing||!exerciseSelect.value;exerciseSelect.disabled=capturing}
exerciseSelect.onchange=syncCapture;
document.querySelector('#clear-capture').onclick=()=>{clearCapture();captureStatus.textContent='Results cleared.'};

captureButton.onclick=async()=>{
 if(!active||capturing||!exerciseSelect.value)return;
 const exercise=exerciseSelect.value,frames=[],times=[],captureCanvas=document.createElement('canvas');
 capturing=true;syncCapture();clearTimeout(timer);controller?.abort();clearCapture();
 // Invalidate the outstanding recognition request without stopping the camera.
 generation++;const captureToken=generation;
 try{
  const started=performance.now();let previousVideoTime=-1;
  while(performance.now()-started<6000){
   if(!active||captureToken!==generation)return;
   if(video.readyState>=2&&video.videoWidth&&video.currentTime!==previousVideoTime){
    previousVideoTime=video.currentTime;
    const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
    captureCanvas.width=Math.round(video.videoWidth*scale);captureCanvas.height=Math.round(video.videoHeight*scale);
    captureCanvas.getContext('2d').drawImage(video,0,0,captureCanvas.width,captureCanvas.height);
    const timestamp=performance.now()-started;
    const blob=await new Promise(resolve=>captureCanvas.toBlob(resolve,'image/jpeg',.85));
    if(!blob)throw Error('Could not read camera frame.');frames.push(blob);times.push(timestamp);
   }
   captureStatus.textContent=`Capturing ${names[exercise]} · ${Math.min(6,(performance.now()-started)/1000).toFixed(1)} / 6 seconds`;
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  if(frames.length<3)throw Error('Too few camera frames. Please capture again.');
  captureStatus.textContent=`Extracting features from ${frames.length} frames…`;
  const form=new FormData();form.append('exercise',exercise);form.append('timestamps',JSON.stringify(times));frames.forEach(blob=>form.append('files',blob,'frame.jpg'));
  captureController=new AbortController();const timeout=setTimeout(()=>captureController?.abort(),60000);let response;
  try{response=await fetch('/capture/features',{method:'POST',body:form,signal:captureController.signal})}finally{clearTimeout(timeout)}
  if(!active||captureToken!==generation)return;
  const result=await response.json();if(!response.ok)throw Error(result.detail||'Feature extraction failed.');
  document.querySelector('#feature-json').textContent=JSON.stringify(result,null,2);document.querySelector('#feature-details').hidden=false;document.querySelector('#feature-details').open=true;
  for(const index of result.review_frame_indices){const figure=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption');const url=URL.createObjectURL(frames[index]);reviewUrls.push(url);img.src=url;img.alt=`Captured movement at ${(times[index]/1000).toFixed(2)} seconds`;caption.textContent=`${(times[index]/1000).toFixed(2)} s`;figure.append(img,caption);document.querySelector('#reviews').append(figure)}
  captureStatus.textContent=result.status==='features_available'?`Features extracted · ${frames.length} timestamped frames. Review images show first usable, observed extreme, and last usable frames (duplicates omitted).`:'Unable to extract features. Check body visibility and capture again.';
 }catch(error){if(captureToken===generation)captureStatus.textContent=error.name==='AbortError'?'Feature extraction timed out. Please capture again.':error.message}
 finally{frames.length=0;if(captureToken===generation){capturing=false;captureController=null;syncCapture();if(active)loop(generation)}}
};

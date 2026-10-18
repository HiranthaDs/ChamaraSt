import { API_BASE } from '../api';

export function workflowApi(actor) {
  const headers = {'Content-Type':'application/json','X-Demo-Role':actor?.role || '', 'X-Demo-Employee-Id':actor?.employeeId || ''};
  async function request(path, method='GET', body) {
    if(method!=='GET') {
      const checkpoint={promise:Promise.resolve()};
      window.dispatchEvent(new CustomEvent('orbit:flush-workspace',{detail:checkpoint}));
      await checkpoint.promise;
    }
    const response = await fetch(`${API_BASE}${path}`, {method,headers,body:body===undefined?undefined:JSON.stringify(body)});
    const result = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(Array.isArray(result.detail) ? result.detail.map(e=>`${e.loc?.slice(1).join('.')}: ${e.msg}`).join('; ') : result.detail || `Request failed (${response.status})`);
    return result;
  }
  async function download(path,filename) {
    const response=await fetch(`${API_BASE}${path}`,{headers});
    if(!response.ok) throw new Error('You cannot download this document. Refresh and try again.');
    const url=URL.createObjectURL(await response.blob()); const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return {request,download};
}

export async function filePayload(file) {
  if(!file || file.size>5*1024*1024) throw new Error('Choose a document no larger than 5 MB.');
  const extension=file.name.split('.').at(-1).toLowerCase();
  const type={pdf:'application/pdf',png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',step:'application/step',stp:'application/step',dxf:'application/dxf'}[extension];
  if(!type) throw new Error('Supported files: PDF, PNG, JPEG, STEP, and ASCII DXF.');
  const content=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
  return {filename:file.name,mime_type:type,content_base64:content};
}

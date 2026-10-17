import"./CWj6FrbW.js";import"./69_IOA4Y.js";import{p as Be,g as Fe,m as L,x as Ve,n as o,j as d,B as je,l as le,A as Ne,i as Ue,c as h,r as w,k as J,t as P,u as W,a as I,d as Ge,o as de,b as Oe,s as $e,aU as fe,f as B,e as Q,a6 as He}from"./MECnX099.js";import{i as Xe}from"./cGGas8gN.js";import{e as Ke,i as Ze}from"./CiyaMMH_.js";import{s as Je}from"./WGVzfzeI.js";import{s as q,a as Pe}from"./CqPDbGo8.js";import{b as Qe}from"./CoAqbVA-.js";import{i as Ye}from"./BPN-Tjdb.js";import{p}from"./DiLvOL-c.js";import{t as z}from"./BH6KUgJ9.js";import{k as ue,x as et,c as tt,i as ot,N as rt}from"./By45c1v5.js";import{t as at}from"./C-k9kX2c.js";import{X as it}from"./E3Nzi1_0.js";var nt=B('<div class="flex items-center h-full"><div></div></div>'),st=B(`<div class=" text-gray-500 rounded-full cursor-not-allowed"><svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor"><style>.spinner_OSmW {
								transform-origin: center;
								animation: spinner_T6mA 0.75s step-end infinite;
							}
							@keyframes spinner_T6mA {
								8.3% {
									transform: rotate(30deg);
								}
								16.6% {
									transform: rotate(60deg);
								}
								25% {
									transform: rotate(90deg);
								}
								33.3% {
									transform: rotate(120deg);
								}
								41.6% {
									transform: rotate(150deg);
								}
								50% {
									transform: rotate(180deg);
								}
								58.3% {
									transform: rotate(210deg);
								}
								66.6% {
									transform: rotate(240deg);
								}
								75% {
									transform: rotate(270deg);
								}
								83.3% {
									transform: rotate(300deg);
								}
								91.6% {
									transform: rotate(330deg);
								}
								100% {
									transform: rotate(360deg);
								}
							}</style><g class="spinner_OSmW"><rect x="11" y="1" width="2" height="5" opacity=".14"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(30 12 12)" opacity=".29"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(60 12 12)" opacity=".43"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(90 12 12)" opacity=".57"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(120 12 12)" opacity=".71"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(150 12 12)" opacity=".86"></rect><rect x="11" y="1" width="2" height="5" transform="rotate(180 12 12)"></rect></g></svg></div>`),ct=B('<button id="confirm-recording-button" type="button" class="p-1.5 bg-indigo-500 text-white dark:bg-indigo-500 dark:text-blue-950 rounded-full"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="size-4"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5"></path></svg></button>'),lt=B('<div><div class="flex items-center mr-1"><button type="button"><!></button></div> <div class="flex flex-1 self-center items-center justify-between ml-2 mx-1 overflow-hidden h-6" dir="rtl"><div class="flex items-center gap-0.5 h-6 w-full max-w-full overflow-hidden overflow-x-hidden flex-wrap"></div></div> <div class="flex"><div class="  mx-1.5 pr-1 flex justify-center items-center"><div> </div></div> <div class="flex items-center"><!></div></div></div>');function St(ge,m){Be(m,!1);const x=()=>Q(ve,"$i18n",V),Y=()=>Q(tt,"$config",V),F=()=>Q(ot,"$settings",V),[V,me]=$e();ue.extend(et);const ve=Fe("i18n");let u=p(m,"recording",12,!1),ee=p(m,"transcribe",8,!0),we=p(m,"displayMedia",8,!1),he=p(m,"echoCancellation",8,!0),pe=p(m,"noiseSuppression",8,!0),ye=p(m,"autoGainControl",8,!0),be=p(m,"className",8," p-2.5 w-full max-w-full"),j=p(m,"onCancel",8,()=>{}),N=p(m,"onConfirm",8,e=>{}),l=L(!1),E=!1,T=L(0),U=null,A="";const ke=()=>{U=setInterval(()=>{He(T)},1e3)},xe=()=>{clearInterval(U),d(T,0)},_e=e=>{const t=Math.floor(e/60),r=e%60,i=r<10?`0${r}`:r;return`${t}:${i}`};let S=null;const te=async()=>{if("wakeLock"in navigator)try{S=await navigator.wakeLock.request("screen"),S.addEventListener("release",()=>{})}catch(e){}},G=async()=>{if(S){try{await S.release()}catch(e){}S=null}};let g,f,v,_=[];const Se=-45;let k=300,n=L(Array(k).fill(0));const Ce=e=>{let t=0;for(let r=0;r<e.length;r++){const i=(e[r]-128)/128;t+=i*i}return Math.sqrt(t/e.length)},Me=e=>{e=e*10;const r=Math.pow(e,1.5);return Math.min(1,Math.max(.01,r))},Re=e=>{const t=new AudioContext,r=t.createMediaStreamSource(e),i=t.createAnalyser();i.minDecibels=Se,r.connect(i);const a=i.frequencyBinCount,s=new Uint8Array(a),c=new Uint8Array(i.fftSize);(()=>{const b=()=>{if(!(!u()||o(l))){if(u()&&!o(l)){i.getByteTimeDomainData(c),i.getByteFrequencyData(s);const R=Ce(c);o(n).push(Me(R)),o(n).length>=k&&o(n).shift(),d(n,o(n))}window.requestAnimationFrame(b)}};window.requestAnimationFrame(b)})()},Le=async(e,t="wav")=>{var i,a,s,c,y,b;await fe();const r=rt(e,`Recording-${ue().locale(x().language).format("L LT")}.${t}`);if(ee()){if(Y().audio.stt.engine==="web"||(((s=(a=(i=F())==null?void 0:i.audio)==null?void 0:a.stt)==null?void 0:s.engine)??"")==="web")return;const R=await at(localStorage.token,r,(b=(y=(c=F())==null?void 0:c.audio)==null?void 0:y.stt)==null?void 0:b.language).catch(ze=>(z.error(`${ze}`),null));R&&N()(R)}else N()({file:r,blob:e})},Ee=async()=>{var t,r,i;d(l,!0);try{if(we()){const a=await navigator.mediaDevices.getDisplayMedia({audio:!0});g=new MediaStream;for(const s of a.getAudioTracks())g.addTrack(s);for(const s of a.getVideoTracks())s.stop()}else g=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:he(),noiseSuppression:pe(),autoGainControl:ye()}})}catch(a){z.error(x().t("Error accessing media devices.")),d(l,!1),u(!1);return}const e=["audio/webm; codecs=opus","audio/webm","audio/ogg; codecs=opus","audio/mp4","audio/wav"];v=new MediaRecorder(g,{mimeType:e.find(a=>MediaRecorder.isTypeSupported(a))}),v.onstart=async()=>{d(l,!1),ke(),await te(),_=[],Re(g)},v.ondataavailable=a=>_.push(a.data),v.onstop=async()=>{var a;if(E){let s=((a=_[0])==null?void 0:a.type)||v.mimeType||"audio/webm",c=s.split("/")[1].split(";")[0]||"webm";s.startsWith("audio/")||(c="webm");const y=new Blob(_,{type:s});await Le(y,c),E=!1,d(l,!1)}_=[],u(!1)};try{v.start()}catch(a){z.error(x().t("Error starting recording.")),d(l,!1),u(!1);return}if(ee()&&(Y().audio.stt.engine==="web"||(((i=(r=(t=F())==null?void 0:t.audio)==null?void 0:r.stt)==null?void 0:i.engine)??"")==="web")&&("SpeechRecognition"in window||"webkitSpeechRecognition"in window)){A="",f=new(window.SpeechRecognition||window.webkitSpeechRecognition),f.continuous=!0,f.interimResults=!0;const a=2e3;let s;f.start(),f.onresult=async c=>{var y;clearTimeout(s);for(const b of Array.from(c.results).slice(c.resultIndex))b.isFinal&&(A=`${A}${b[0].transcript}`);await fe(),(y=document.getElementById("chat-input"))==null||y.focus(),s=setTimeout(()=>{f.stop()},a)},f.onend=function(){re(),N()({text:A}),E=!1,d(l,!1)},f.onerror=function(c){z.error(x().t("Speech recognition error: {{error}}",{error:c.error})),j()(),O()}}},O=async()=>{f&&(f.onend=null),await oe()},oe=async()=>{u()&&v&&await v.stop(),f&&f.stop(),await G(),xe(),_=[],d(n,Array(k).fill(0)),g&&g.getTracks().forEach(t=>t.stop()),g=null},re=async()=>{d(l,!0),E=!0,u()&&v&&await v.stop(),clearInterval(U),await G(),g&&g.getTracks().forEach(t=>t.stop()),g=null};let $,H=L(),Te=L(300);const ae=e=>{u()&&e.key==="Escape"&&(e.preventDefault(),O(),j()())},ie=async()=>{u()&&document.visibilityState==="visible"&&await te()};Ve(()=>{window.addEventListener("keydown",ae),document.addEventListener("visibilitychange",ie),$=new ResizeObserver(()=>{k=Math.floor(window.innerWidth/4),o(n).length>k?d(n,o(n).slice(o(n).length-k)):d(n,Array(k-o(n).length).fill(0).concat(o(n)))}),$.observe(document.body)}),je(()=>{window.removeEventListener("keydown",ae),document.removeEventListener("visibilitychange",ie),G(),$.disconnect()}),le(()=>Ne(u()),()=>{u()?Ee():oe()}),le(()=>o(H),()=>{d(Te,Math.floor(o(H)/5))}),Ue(),Ye();var C=lt(),X=h(C),D=h(X),Ae=h(D);it(Ae,{className:"size-4"}),w(D),w(X);var M=J(X,2),ne=h(M);Ke(ne,5,()=>(o(n),W(()=>o(n).slice().reverse())),Ze,(e,t)=>{var r=nt(),i=h(r);w(r),P(a=>{q(i,1,`w-[0.125rem] shrink-0
                    
                    ${o(l)?" bg-gray-500 dark:bg-gray-400   ":"bg-indigo-500 dark:bg-indigo-400  "} 
                    
                    inline-block h-full`),Pe(i,`height: ${a??""}%;`)},[()=>(o(t),W(()=>Math.min(100,Math.max(14,o(t)*100))))]),I(e,r)}),w(ne),w(M);var se=J(M,2),K=h(se),Z=h(K),De=h(Z,!0);w(Z),w(K);var ce=J(K,2),We=h(ce);{var Ie=e=>{var t=st();I(e,t)},qe=e=>{var t=ct();P(r=>Je(t,"aria-label",r),[()=>(x(),W(()=>x().t("Confirm recording")))]),de("click",t,async()=>{await re()}),I(e,t)};Xe(We,e=>{o(l)?e(Ie):e(qe,-1)})}w(ce),w(se),w(C),P(e=>{q(C,1,`${o(l)?" bg-gray-100/50 dark:bg-gray-850/50":"bg-indigo-300/10 dark:bg-indigo-500/10 "} rounded-full flex justify-between ${be()??""}`,"svelte-nkn4fu"),q(D,1,`p-1.5

            ${o(l)?" bg-gray-200 dark:bg-gray-700/50":"bg-indigo-400/20 text-indigo-600 dark:text-indigo-300 "} 


             rounded-full`),M.dir=M.dir,q(Z,1,`text-sm
        
        
        ${o(l)?" text-gray-500  dark:text-gray-400  ":" text-indigo-400 "} 
       font-normal flex-1 mx-auto text-center`),Ge(De,e)},[()=>(o(T),W(()=>_e(o(T))))]),de("click",D,async()=>{O(),j()()}),Qe(C,"clientWidth",e=>d(H,e)),I(ge,C),Oe(),me()}export{St as V};
//# sourceMappingURL=sMyuV7HV.js.map

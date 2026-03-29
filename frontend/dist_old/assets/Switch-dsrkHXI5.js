import{j as n}from"./vendor-react-DoyxvGH4.js";function m({checked:t,onChange:e,label:a,size:r="md",disabled:s}){const i=r==="sm"?"h-5 w-9":"h-6 w-11",o=r==="sm"?"h-3.5 w-3.5":"h-5 w-5",l=r==="sm"?"translate-x-4":"translate-x-5";return n.jsxs("label",{className:`inline-flex items-center gap-2.5 ${s?"opacity-50":"cursor-pointer"}`,children:[n.jsx("button",{role:"switch","aria-checked":t,disabled:s,onClick:()=>!s&&e(!t),className:`
          relative inline-flex ${i} items-center rounded-full transition-colors duration-200
          ${t?"bg-primary-600":"bg-white/10"}
          cursor-pointer
        `,children:n.jsx("span",{className:`
            inline-block ${o} rounded-full bg-white shadow-md
            transform transition-transform duration-200
            ${t?l:"translate-x-0.5"}
          `})}),a&&n.jsx("span",{className:"text-sm text-starlight-200 select-none",children:a})]})}export{m as S};

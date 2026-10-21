import * as React from 'react';
import {createRoot} from 'react-dom/client';
import AldolUI from './Generated';
createRoot(document.getElementById('root')!).render(<AldolUI values={{'project-count':21,'qa-status':'READY','work-progress':87}} onAction={a=>{document.body.dataset.action=a.name}}/>);

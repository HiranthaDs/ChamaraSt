import assert from 'node:assert/strict';
import {historyChange,historyUndo,historyRedo,partGeometry} from '../src/manufacturing/cutting-client.js';
let h={past:[],present:[{x:1}],future:[]};h=historyChange(h,[{x:10}]);h=historyChange(h,[{x:20}]);
assert.equal(historyUndo(h).present[0].x,10);assert.equal(historyRedo(historyUndo(h)).present[0].x,20);
assert.equal(historyChange(historyUndo(h),[{x:50}]).future.length,0);
const circle=partGeometry({shape:'circle',diameter:200},{x:10,y:20,rotation:0});assert.equal(circle.cx,110);assert.equal(circle.cy,120);assert.equal(circle.r,100);
const rect=partGeometry({shape:'rectangle',w:300,h:150},{x:10,y:20,rotation:90});assert.ok(Math.abs(rect.w-150)<1e-6);assert.equal(rect.h,300);
console.log('Cutting editor history and scaled geometry checks passed.');

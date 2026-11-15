const test=require('node:test'),assert=require('node:assert/strict');
const math=require('../web/drive_math.js');
test('joystick forward, reverse and turning signs',()=>{
  assert.deepEqual(math.stickVector(0,0),[0,0,0]);
  assert.deepEqual(math.stickVector(.02,.02),[0,0,0]);
  assert.equal(math.stickVector(0,-1)[0],1);
  assert.equal(math.stickVector(0,1)[0],-1);
  assert.equal(math.stickVector(1,0)[2],-1);
  assert.equal(math.stickVector(-1,0)[2],1);
});
test('omni buttons translate without turning and diagonal input stays bounded',()=>{
  assert.deepEqual(math.combine([[0,1,0]],.03,.1),[0,.03,0]);
  assert.deepEqual(math.combine([[0,-1,0]],.03,.1),[0,-.03,0]);
  const v=math.combine([[1,0,1],[0,1,0]],.03,.1);
  assert.ok(Math.abs(Math.hypot(...v.slice(0,2))-.03)<1e-10);assert.equal(v[2],.1);
});
test('front scan projects up, robot left projects left, independent of map heading',()=>{
  const points=math.cameraPoints([[0,.5],[-1,0]],[0,0,-Math.PI/2],0);
  const front=math.projectPoint(points[0],150,100,50),left=math.projectPoint(points[1],150,100,50);
  assert.ok(Math.abs(front[0]-150)<1e-10);assert.equal(front[1],75);
  assert.equal(left[0],100);assert.ok(Math.abs(left[1]-100)<1e-10);
  assert.equal(math.sectorDistance(points,0),.5);
});

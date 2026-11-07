if (!process.argv.includes('--web-only')) {
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const root = path.resolve(__dirname, '../..');
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!fs.existsSync(python)) {
  console.error('Set up the root .venv first. See frontend/README.md.'); process.exit(1);
}
const api = spawn(python, [path.join(__dirname, '../BACKEND/run.py')], { stdio: 'inherit', windowsHide: true });
let web;
let stopping = false;
function stop(code = 0) {
  if (stopping) return; stopping = true;
  if (web) web.kill(); api.kill(); setTimeout(() => process.exit(code), 100);
}
api.on('error', error => { console.error(error.message); stop(1); });
api.on('exit', code => { if (!stopping) stop(code || 1); });
async function launch() {
  for (let attempt = 0; attempt < 80; attempt++) {
    if (stopping) return;
    try {
      const response = await fetch('http://127.0.0.1:8000/health');
      if (response.ok) {
        web = spawn(process.execPath, [__filename, '--web-only'], { stdio: 'inherit', windowsHide: true });
        web.on('exit', code => stop(code || 0)); return;
      }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  console.error('API did not start; check the error above.'); stop(1);
}
process.on('SIGINT', () => stop()); process.on('SIGTERM', () => stop()); launch();

} else {
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = __dirname;
const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp' };
http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) {
    let size = 0;
    const proxy = http.request({ hostname: '127.0.0.1', port: 8000, path: req.url, method: req.method,
      headers: { ...req.headers, host: '127.0.0.1:8000' } }, upstream => {
      res.writeHead(upstream.statusCode, upstream.headers); upstream.pipe(res);
    });
    proxy.on('error', () => {
      if (!res.headersSent) { res.writeHead(503, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ error: 'campus API is offline. start the full app with npm.cmd start.' })); }
      else res.end();
    });
    req.on('data', chunk => { size += chunk.length; if (size > 6500000) { proxy.destroy(); req.destroy(); } });
    req.pipe(proxy);
    return;
  }
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const file = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (error, body) => {
    if (error) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(body);
  });
}).listen(Number(process.env.PORT || 3000), '127.0.0.1', () => console.log('local preview: http://localhost:' + (process.env.PORT || 3000)));

}

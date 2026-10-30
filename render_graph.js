const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

// Render the Mermaid source locally using Chromium and the installed Mermaid bundle.
async function Render_Picture(source, output, installDir, browserPath, timeout, background, sizeLimit, header, port) {
    if (!Number.isInteger(timeout) || timeout <= 0) throw new Error('timeout must be a positive integer');
    if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('invalid HTTP port');
    if (!Number.isInteger(sizeLimit) || sizeLimit <= 0) throw new Error('invalid diagram size limit');
    if (!Buffer.isBuffer(header) || header.length !== 8) throw new Error('invalid PNG signature');
    if (typeof background !== 'string' || !background.trim()) throw new Error('background color is required');
    if (typeof installDir !== 'string' || !installDir.trim()) throw new Error('Mermaid installation path is required');
    if (typeof source !== 'string') throw new Error('mermaid must be a string');
    if (!source.trim()) throw new Error('mermaid must not be empty');
    if (source.length > sizeLimit) throw new Error('mermaid is too large');
    if (!/^\s*(graph|flowchart)\s+(TD|TB|LR|RL|BT)\b/.test(source)) throw new Error('unsupported Mermaid graph');
    if (typeof output !== 'string' || !output.trim()) throw new Error('output_png is required');
    if (path.extname(output).toLowerCase() !== '.png') throw new Error('output_png must have PNG extension');
    if (!fs.existsSync(browserPath)) throw new Error(`Chromium missing: ${browserPath}`);
    const bundle = path.join(installDir, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js');
    const puppeteerPath = path.join(installDir, 'node_modules', 'puppeteer-core');
    if (!fs.existsSync(bundle)) throw new Error(`Mermaid bundle missing: ${bundle}`);
    if (!fs.existsSync(puppeteerPath)) throw new Error(`Puppeteer missing: ${puppeteerPath}`);
    const target = path.resolve(output);
    const parent = path.dirname(target);
    if (!fs.existsSync(parent) || !fs.statSync(parent).isDirectory()) throw new Error(`output directory missing: ${parent}`);
    if (fs.existsSync(target) && fs.statSync(target).isDirectory()) throw new Error('output_png is a directory');
    const puppeteer = require(puppeteerPath);
    const pageHtml = '<!doctype html><html><head><meta charset="utf-8"></head><body><div id="graph"></div><script src="/mermaid.js"></script></body></html>';
    const server = http.createServer((request, response) => {
        if (request.url === '/') { response.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'}); response.end(pageHtml); }
        else if (request.url === '/mermaid.js') { response.writeHead(200, {'Content-Type': 'application/javascript; charset=utf-8'}); fs.createReadStream(bundle).pipe(response); }
        else { response.writeHead(404); response.end(); }
    });
    let browser;
    try {
        await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
        browser = await puppeteer.launch({executablePath: browserPath, headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']});
        const page = await browser.newPage();
        page.setDefaultTimeout(timeout);
        await page.goto(`http://127.0.0.1:${server.address().port}/`, {waitUntil: 'load', timeout});
        await page.evaluate(async (diagram, color) => {
            document.body.style.backgroundColor = color;
            window.mermaid.initialize({startOnLoad: false, securityLevel: 'strict'});
            const rendered = await window.mermaid.render('dependency_graph', diagram);
            document.getElementById('graph').innerHTML = rendered.svg;
        }, source, background);
        const image = await page.$('#graph svg');
        if (!image) throw new Error('Mermaid produced no SVG');
        const bytes = Buffer.from(await image.screenshot({type: 'png'}));
        if (bytes.length < 24) throw new Error('renderer produced a truncated PNG');
        if (!bytes.subarray(0, 8).equals(header)) throw new Error('renderer produced invalid PNG');
        if (bytes.readUInt32BE(16) === 0 || bytes.readUInt32BE(20) === 0) throw new Error('renderer produced an empty PNG');
        fs.writeFileSync(target, bytes);
        return target;
    } finally {
        if (browser) await browser.close();
        await new Promise(resolve => server.close(resolve));
    }
}

(async () => {
    try {
        const data = JSON.parse(fs.readFileSync(0, 'utf8'));
        const installDir = process.env.MERMAID_INSTALL_DIR || '/workspace/toolchains/mermaid';
        const browser = process.env.CHROMIUM_PATH || '/usr/bin/chromium';
        const output_png = await Render_Picture(data.mermaid, data.output_png, installDir, browser, 120000, 'white', 10000000, Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), 0);
        process.stdout.write(JSON.stringify({output_png}));
    } catch (error) {
        process.stderr.write(`PNG render: ${error.message}\n`);
        process.exitCode = 1;
    }
})();

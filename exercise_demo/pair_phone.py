"""Local pairing helper: serves only a setup page and the PUBLIC demo CA."""
import argparse
import html
import plistlib
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import qrcode

ROOT = Path(__file__).resolve().parent.parent

def profile(certificate):
    identity = uuid.uuid5(uuid.NAMESPACE_URL, certificate.hex())
    return plistlib.dumps({
        'PayloadContent': [{
            'PayloadCertificateFileName': 'move-demo-ca.cer',
            'PayloadContent': certificate,
            'PayloadDescription': 'Local certificate for the Move exercise camera demo.',
            'PayloadDisplayName': 'Move Local Demo CA',
            'PayloadIdentifier': 'local.move.demo.ca',
            'PayloadType': 'com.apple.security.root',
            'PayloadUUID': str(identity), 'PayloadVersion': 1,
        }],
        'PayloadDisplayName': 'Move Camera Demo',
        'PayloadDescription': 'Installs the local demo certificate. Enable trust manually to use the HTTPS camera app. Remove this profile after testing.',
        'PayloadIdentifier': 'local.move.demo', 'PayloadRemovalDisallowed': False,
        'PayloadType': 'Configuration', 'PayloadUUID': str(uuid.uuid5(identity, 'profile')),
        'PayloadVersion': 1,
    })

def make_handler(host):
    app_url = f'https://{host}:8443'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/','/setup'):
                body = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Connect your phone</title>
<style>body{{font:18px system-ui;max-width:600px;margin:32px auto;padding:20px;line-height:1.6}}a{{display:block;margin:16px 0;padding:14px;background:#18241e;color:white;border-radius:12px;text-decoration:none}}li{{margin:14px 0}}</style>
<h1>Connect your phone</h1><p>Keep your phone and Mac on the same network. The Mac runs recognition; the phone supplies camera frames. Frames are not saved by the app.</p>
<h2>iPhone</h2><ol><li><a href="/move-demo.mobileconfig">Download demo certificate profile</a>Use Safari. Allow the profile download.</li><li>Open Settings → General → VPN &amp; Device Management → Move Camera Demo → Install.</li><li>Open Settings → General → About → Certificate Trust Settings. Enable <strong>Move Local Demo CA</strong>.</li></ol>
<h2>Android</h2><p><a href="/move-demo-ca.cer">Download demo CA certificate</a>Install as a CA certificate in Settings → Security → Encryption &amp; credentials (wording varies).</p>
<h2>Start testing</h2><a href="{html.escape(app_url)}">Open exercise camera</a><p>Tap Start camera and allow access. The output is Squat, Push-up, Lateral raise, or Unknown.</p><p>This installs a local certificate authority for this demo. Remove its profile/trust after testing. No Mac certificate trust is changed.</p></html>'''.encode()
                mime = 'text/html; charset=utf-8'
                filename = None
            elif self.path in ('/move-demo-ca.cer','/move-demo.mobileconfig'):
                certificate = (ROOT/'.cache/tls/move-demo-ca.cer').read_bytes()
                filename = self.path[1:]
                body = profile(certificate) if filename.endswith('mobileconfig') else certificate
                mime = 'application/x-apple-aspen-config' if filename.endswith('mobileconfig') else 'application/pkix-cert'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
            self.end_headers();self.wfile.write(body)
    return Handler

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--host-ip',required=True);parser.add_argument('--port',type=int,default=8001);args=parser.parse_args()
    import ipaddress
    ipaddress.IPv4Address(args.host_ip)
    url=f'http://{args.host_ip}:{args.port}/setup'
    out=ROOT/'exercise_demo/results/phone-setup-qr.png'
    qrcode.make(url).save(out)
    print(f'Scan {out} or open {url}',flush=True)
    HTTPServer(('0.0.0.0',args.port),make_handler(args.host_ip)).serve_forever()

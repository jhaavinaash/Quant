"""
notifier.py
-----------
Sends daily trading signals to email.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
SENDER_EMAIL   = "jhaavinaash@gmail.com"
SENDER_PASS    = "hsde hkyo vhtm edrl"
RECEIVER_EMAIL = "jhaavinaash@gmail.com"
SMTP_SERVER    = "smtp.gmail.com"
SMTP_PORT      = 587

def send_signal_email(candidates, top_sectors):
    date_str = datetime.now().strftime("%d %b %Y")
    subject  = f"Trading Signal — {date_str} — {len(candidates)} trade(s)"

    if not candidates:
        body = f"""
        <html><body style="font-family:Arial;background:#0f0f0f;color:#ffffff;padding:20px">
        <h2 style="color:#00d4aa">Adaptive Sector Momentum</h2>
        <p style="color:#aaaaaa">Date: {date_str}</p>
        <hr style="border-color:#333">
        <h3 style="color:#ff4444">No Buy Signals Today</h3>
        <p>Market conditions did not meet entry criteria. Wait for next session.</p>
        <hr style="border-color:#333">
        <p style="color:#555;font-size:12px">Active sectors: {', '.join(top_sectors)}</p>
        </body></html>
        """
    else:
        trades_html = ""
        for i, c in enumerate(candidates, 1):
            trades_html += f"""
            <div style="background:#1a1a1a;border:1px solid #333;border-radius:8px;
                        padding:16px;margin:12px 0">
              <h3 style="color:#00d4aa;margin:0 0 4px 0">
                Trade {i} — {c['Ticker']} ({c['Sector']})
              </h3>
              <p style="color:#888;margin:0 0 12px 0;font-size:13px">
                Score: {c['Score']} &nbsp;|&nbsp;
                ADX: {c['ADX']} &nbsp;|&nbsp;
                Vol Ratio: {c['Vol_Ratio']}x
              </p>
              <table style="width:100%;border-collapse:collapse;font-size:14px">
                <tr>
                  <td style="padding:6px 0;color:#aaa;width:140px">Entry (at open)</td>
                  <td style="color:#ffffff;font-weight:bold">&#8377;{c['Entry']}</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#aaa">Stop Loss</td>
                  <td style="color:#ff4444;font-weight:bold">
                    &#8377;{c['SL']} &nbsp;
                    <span style="color:#888;font-size:12px">({c['SL_pct']} from entry)</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#aaa">Target 1 (50%)</td>
                  <td style="color:#00d4aa;font-weight:bold">
                    &#8377;{c['Partial_Target']} &nbsp;
                    <span style="color:#888;font-size:12px">({c['Partial_pct']})</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:6px 0;color:#aaa">Target 2 (trail)</td>
                  <td style="color:#00d4aa;font-weight:bold">
                    &#8377;{c['Full_Target']} &nbsp;
                    <span style="color:#888;font-size:12px">({c['Full_pct']})</span>
                  </td>
                </tr>
                <tr>
                  <td colspan="2"><hr style="border-color:#333;margin:8px 0"></td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#aaa">Shares</td>
                  <td style="color:#fff">{c['Shares']} shares</td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#aaa">Capital Used</td>
                  <td style="color:#fff">{c['Capital_Used']}</td>
                </tr>
                <tr>
                  <td style="padding:4px 0;color:#aaa">Risk</td>
                  <td style="color:#fff">{c['Risk_Rs']} ({c['Risk_Pct']} of capital)</td>
                </tr>
              </table>
            </div>
            """

        body = f"""
        <html><body style="font-family:Arial;background:#0f0f0f;color:#ffffff;padding:20px">
        <h2 style="color:#00d4aa">Adaptive Sector Momentum</h2>
        <p style="color:#aaaaaa">Date: {date_str} &nbsp;|&nbsp;
           Signals: {len(candidates)} &nbsp;|&nbsp;
           Capital: &#8377;1,00,000</p>
        <hr style="border-color:#333">
        {trades_html}
        <hr style="border-color:#333">
        <p style="color:#555;font-size:12px">
          Active sectors: {', '.join(top_sectors)}<br>
          Entry at next market open. Set GTT stop loss immediately after buying.
        </p>
        </body></html>
        """

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"✓ Signal email sent → {RECEIVER_EMAIL}")
    except Exception as e:
        print(f"✗ Email failed — {e}")


if __name__ == "__main__":
    send_signal_email([], ["Healthcare", "Technology", "Industrials"])
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import pdfkit
import jinja2
import os
import requests
import smtplib
from email.message import EmailMessage

app = FastAPI()

# -- Templates Setup --
template_loader = jinja2.FileSystemLoader(searchpath="templates")
template_env = jinja2.Environment(loader=template_loader)

template_file = "soul_blueprint_template.html"

# -- AstroAPI Configuration --
ASTRO_API_KEY = os.getenv("ASTRO_API_KEY")
ASTRO_API_URL = "https://api.astroapi.dev/api/v1/planets"

def get_astrology_data(birth_date, birth_time, birth_place):
    payload = {
        "birth_date": birth_date,
        "birth_time": birth_time,
        "location": birth_place,
        "timezone": "auto"
    }
    headers = {"Authorization": f"Bearer {ASTRO_API_KEY}"}
    response = requests.post(ASTRO_API_URL, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return {
            "sun_sign": data.get("sun", {}).get("sign", "Unknown"),
            "moon_sign": data.get("moon", {}).get("sign", "Unknown"),
            "rising_sign": data.get("ascendant", {}).get("sign", "Unknown")
        }
    else:
        raise Exception("Failed to fetch astrology data.")

def render_pdf_from_template(data):
    template = template_env.get_template(template_file)
    html_content = template.render(data=data)
    output_path = f"reports/{data['name'].replace(' ', '_')}_soul_blueprint.pdf"
    pdfkit.from_string(html_content, output_path)
    return output_path

def send_email_with_attachment(to_email, subject, body, attachment_path):
    msg = EmailMessage()
    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")

    msg['Subject'] = subject
    msg['From'] = email_address
    msg['To'] = to_email
    msg.set_content(body)

    with open(attachment_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(attachment_path)
        msg.add_attachment(file_data, maintype='application', subtype='pdf', filename=file_name)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(email_address, email_password)
        smtp.send_message(msg)

class SoulInput(BaseModel):
    name: str
    birth_date: str
    birth_time: str
    birth_place: str
    email: Optional[str] = None

def calculate_life_path(birth_date):
    digits = [int(d) for d in birth_date if d.isdigit()]
    while sum(digits) > 9 and sum(digits) not in [11, 22, 33]:
        digits = [int(d) for d in str(sum(digits))]
    return sum(digits)

def basic_hd_logic(birth_time):
    hour = int(birth_time.split(":")[0])
    if 6 <= hour < 12:
        return {"type": "Generator", "authority": "Sacral"}
    elif 12 <= hour < 18:
        return {"type": "Projector", "authority": "Emotional"}
    elif 18 <= hour < 22:
        return {"type": "Manifestor", "authority": "Splenic"}
    else:
        return {"type": "Reflector", "authority": "Lunar"}

@app.post("/generate-soul-blueprint")
def generate_blueprint(input_data: SoulInput):
    try:
        life_path = calculate_life_path(input_data.birth_date)
        astrology = get_astrology_data(
            input_data.birth_date, input_data.birth_time, input_data.birth_place
        )
        human_design = basic_hd_logic(input_data.birth_time)

        pdf_path = render_pdf_from_template({
            "name": input_data.name,
            "sun_sign": astrology['sun_sign'],
            "moon_sign": astrology['moon_sign'],
            "rising": astrology['rising_sign'],
            "hd_type": human_design['type'],
            "authority": human_design['authority'],
            "life_path": life_path
        })

        if input_data.email:
            send_email_with_attachment(
                to_email=input_data.email,
                subject="Your Soul Blueprint Report",
                body="Here is your personalized Soul Blueprint report. ✨",
                attachment_path=pdf_path
            )

        return {"message": "Blueprint generated and sent", "pdf_path": pdf_path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

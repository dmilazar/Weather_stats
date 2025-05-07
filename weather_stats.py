from datetime import datetime
from statistics import mean
from collections import Counter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
import json
import requests
import time
import smtplib
import os

load_dotenv()

email_username = os.getenv("EMAIL_USERNAME")
email_password = os.getenv("EMAIL_PASSWORD")
email_to = os.getenv("EMAIL_TO")
git_url = os.getenv("GIT_URL")

class WeatherStats:
    def __init__(self):
        self.weather_stats_url = 'https://hook.eu2.make.com/7mfiayunbpfef8qlnielxli5ptoktz02'
        self.public_holidays_url = 'https://hook.eu2.make.com/76g53ebwgbestjsj1ikejbaicpnc5jro'
        self.json_filename = "json_files/weather_report.json"

    def process_weather_stats(self):
        holiday_api_data = self.get_public_holidays()
        weather_api_data = self.get_weather_stats()

        if holiday_api_data and weather_api_data:
            self.structure_weather_data(weather_api_data, holiday_api_data)

    def structure_weather_data(self, weather_api_data, holiday_api_data):
        # Extract max, min and average temperature degrees for the month
        degrees = [item["degrees_in_celsius"] for item in weather_api_data]
        max_temp = max(degrees)
        min_temp = min(degrees)
        avg_temp = round(mean(degrees), 2)

        # Count unique sky values
        sky_values = [item["sky"] for item in weather_api_data]
        sky_counts = Counter(sky_values)

        # Sort alphabetically and capitalize
        sorted_sky_counts = {k.capitalize(): v for k, v in sorted(sky_counts.items(), key=lambda x: x[0].capitalize())}

        # Rain showers
        all_rain_showers = []
        for day in weather_api_data:
            rain_showers = day.get('times_of_rain_showers')

            if rain_showers:
                date_str = day['date']
                shower_times = [time.strip() for time in day['times_of_rain_showers'].split(',')]

                all_rain_showers.append({'date': date_str, 'rain_showers': shower_times})


        # Match holiday sky statuses
        holiday_skies = {}
        for holiday in holiday_api_data:
            # Find all weather entries for this holiday
            if holiday['is_public_holiday'] == 'yes':
                holiday_skies[holiday['date']] = next((item['sky'] for item in weather_api_data if item['date'] == holiday['date']), "unknown")

        # Save to JSON file
        daily_json = []
        for day in weather_api_data:
            json_data = {
                'sky': day.get('sky'),
                'city': day.get('city'),
                'date': day.get('date'),
                'degrees': day.get('degrees_in_celsius'),
                'is_public_holiday': next(h.get('is_public_holiday') for h in holiday_api_data if h.get('date') == day.get('date')),
                'times_of_rain_showers': next((d.get('rain_showers') for d in all_rain_showers if d.get('date') == day.get('date')), None)
            }

            daily_json.append(json_data)

        with open(self.json_filename, "w") as json_file:
            json.dump(daily_json, json_file, indent=4)

        # Send email
        return self.send_email_with_attachment(max_temp, avg_temp, min_temp, sorted_sky_counts, all_rain_showers,
                               holiday_skies)


    def send_email_with_attachment(self, max_temp, avg_temp, min_temp, sorted_sky_counts, all_rain_showers, holiday_skies):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            email_from = email_username

            message = MIMEMultipart()
            message["From"] = email_from
            message["To"] = email_to
            message["Subject"] = f"Certification Level 4 | Practical Challenge | {email_from} | {timestamp}"

            body = f"### GIT URL: {git_url} ###\n\n"
            body += "Hi,\n"
            body += "Here are your San Francisco weather stats for 2022-11:\n"
            body += f"The max temperature was: {max_temp}\n"
            body += f"The avg temperature was: {avg_temp}\n"
            body += f"The min temperature was: {min_temp}\n\n"

            # Sky counts
            body += "Overview of unique 'sky' values and their counts:\n"
            for sky_type, count in sorted_sky_counts.items():
                body += f"{sky_type} {count}\n"

            if all_rain_showers:
                body += "\nRain showers:\n"
                for shower in all_rain_showers:
                    shower_date = shower.get('date')
                    for time in shower.get('rain_showers', []):
                        body += f"{shower_date} {time}\n"
            else:
                body += "\nThere was no rain showers this month.\n"

            if holiday_skies:
                body += "\n'Sky' statuses during holidays:\n"
                for date, sky_type in holiday_skies.items():
                    body += f"{date} {sky_type}\n"

            body += "\nHave a nice day!\n"

            # Attach the body
            message.attach(MIMEText(body, "plain"))

            # Attach the JSON file
            with open(self.json_filename, "rb") as attachment:
                mime_base = MIMEBase("application", "octet-stream")
                mime_base.set_payload(attachment.read())
                encoders.encode_base64(mime_base)
                mime_base.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(self.json_filename)}",
                )
                message.attach(mime_base)

            # Send the email
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login(email_from, email_password)
                server.sendmail(email_from, email_to, message.as_string())
                print("Email sent successfully!")

        except FileNotFoundError:
            print(f"Attachment file {self.json_filename} not found.")

        except Exception as e:
            print(f"Failed to send email: {e}")


    def get_weather_stats(self):
        try:
            response = requests.get(self.weather_stats_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # print("Weather data:", data)
                return data
            else:
                print(f"Failed to fetch weather data. Status code: {response.status_code}")

        except requests.RequestException as e:
            print(f"Error occurred while fetching weather data: {e}")

    def get_public_holidays(self, max_retries=5):
        retries = 0

        while retries <= max_retries:
            try:
                response = requests.get(self.public_holidays_url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    # print("Holidays data:", data)
                    return data
                elif response.status_code == 429:
                    retries += 1
                    wait_time = 10  # Fixed 10 second wait

                    if retries <= max_retries:
                        print(
                            f"429 Error, rate limit hit. Retrying in {wait_time} seconds... ({retries}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Maximum retries ({max_retries}) reached. Giving up.")
                        return None
                else:
                    print(f"Failed to fetch public holidays. Status code: {response.status_code}")
                    return None

            except requests.RequestException as e:
                print(f"Error occurred while fetching public holidays: {e}")
                return None


weather_stats = WeatherStats()
weather_data = weather_stats.process_weather_stats()


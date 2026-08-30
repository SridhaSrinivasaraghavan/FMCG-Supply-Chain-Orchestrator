import requests

data = {'news_text': 'Annual marathon on NH-44 near Bangalore announced for tomorrow. Total road closure from 6 AM to 2 PM. Heavy traffic expected post-marathon.'}
response = requests.post('http://localhost:8000/api/trigger-disruption', json=data)
print(response.text)

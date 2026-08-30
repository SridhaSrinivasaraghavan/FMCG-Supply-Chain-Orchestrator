import random

class DisruptionStreamer:
    """
    Mock service to simulate incoming disruption alerts from external sources
    (e.g., RSS feeds, OpenWeather API, transport APIs).
    """
    
    MOCK_EVENTS = [
        {
            "news_text": "Massive monsoon floods in the North region have completely washed out major highways. Freight transport is halted.",
            "region": "North"
        },
        {
            "news_text": "Port workers strike in the West region delays all incoming oil and fat shipments for at least a week.",
            "region": "West"
        },
        {
            "news_text": "Sudden heatwave and crop failure in the East severely impacts sugar yield, driving up local prices and tightening supply.",
            "region": "East"
        },
        {
            "news_text": "Major railway derailment in the South causes a multi-day backlog for all industrial additives and baking supplies.",
            "region": "South"
        }
    ]
    
    @classmethod
    def get_latest(cls):
        """Returns a random realistic disruption event for demo purposes."""
        return random.choice(cls.MOCK_EVENTS)

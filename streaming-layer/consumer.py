"""Read a finite number of flight-realtime messages from the beginning."""
import argparse
import json
import os
from dotenv import load_dotenv
from kafka import KafkaConsumer

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-messages', type=int, default=10)
    args = parser.parse_args()
    consumer = KafkaConsumer(
        os.environ.get('KAFKA_TOPIC', 'flight-realtime'),
        bootstrap_servers=os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'localhost:29092'),
        auto_offset_reset='earliest', group_id=None, enable_auto_commit=False,
        consumer_timeout_ms=10000,
        value_deserializer=lambda b: json.loads(b.decode('utf-8')),
    )
    count = 0
    try:
        for msg in consumer:
            print(f'partition={msg.partition} offset={msg.offset}\n{json.dumps(msg.value, indent=2, ensure_ascii=False)}')
            count += 1
            if count >= args.max_messages:
                break
    finally:
        consumer.close()
    print(f'READ {count} message(s)')


if __name__ == '__main__':
    main()

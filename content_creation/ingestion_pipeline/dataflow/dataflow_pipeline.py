import argparse
import json
import logging

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

class ParsePubSubMessage(beam.DoFn):
    def process(self, message):
        try:
            # message is bytes, decode and load JSON
            payload = message.decode('utf-8')
            yield json.loads(payload)
        except Exception as e:
            logging.error(f"Failed to parse message: {e}")

def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input_topic',
        required=True,
        help='Input Pub/Sub topic of the form "projects/<PROJECT>/topics/<TOPIC>".'
    )
    parser.add_argument(
        '--output_table',
        required=True,
        help='Output BigQuery table for results specified as: PROJECT:DATASET.TABLE or DATASET.TABLE.'
    )
    
    known_args, pipeline_args = parser.parse_known_args(argv)
    
    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=pipeline_options) as p:
        (
            p
            | "Read from Pub/Sub" >> beam.io.ReadFromPubSub(topic=known_args.input_topic)
            | "Parse JSON payload" >> beam.ParDo(ParsePubSubMessage())
            | "Write to BigQuery" >> beam.io.WriteToBigQuery(
                known_args.output_table,
                create_disposition=beam.io.BigQueryDisposition.CREATE_NEVER,
                write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                method='STREAMING_INSERTS'
            )
        )

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    run()

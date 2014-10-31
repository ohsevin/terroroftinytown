import argparse
import json
import logging
import os.path
import sys
import time

from terroroftinytown.release.iaupload import IAUploaderBootstrap
from terroroftinytown.tracker.export import ExporterBootstrap
from terroroftinytown.tracker.bootstrap import Bootstrap


logger = logging.getLogger(__name__)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('config_path')
    arg_parser.add_argument('export_dir',
                            default='/home/tinytown/tinytown-export/')
    arg_parser.add_argument('--verbose', action='store_true')

    args = arg_parser.parse_args()

    if not os.path.exists(args.export_dir):
        os.mkdir(args.export_dir)

    log_filename = os.path.join(args.export_dir, 'supervisor.log')
    logging.basicConfig(level=logging.INFO, filename=log_filename)

    if args.verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        stream_handler.setFormatter(formatter)
        logging.getLogger().addHandler(stream_handler)

    logger.info('Supervisor starting up.')

    try:
        wrapper(args.config_path, args.export_dir)
    except (Exception, SystemExit):
        logger.exception('Failure.')
        raise

    logger.info('Supervisor done.')


def wrapper(config_path, export_dir):
    sentinel_file = os.path.join(export_dir, 'tinytown-supervisor-sentinel')

    if os.path.exists(sentinel_file):
        raise Exception(
            'The sentinel file exists. '
            'Previous supervisor did not exit correctly.'
            )
    else:
        with open(sentinel_file, 'wb'):
            pass

    if sys.version_info[0] != 3:
        raise Exception('This script expects Python 3')

    if not os.path.isfile(config_path):
        raise Exception('Config path is not a file.')

    logger.info('Loading bootstrap.')

    bootstrap = Bootstrap()
    bootstrap.setup_args()
    bootstrap.parse_args(args=[config_path])
    bootstrap.load_config()

    time_struct = time.gmtime()
    timestamp = bootstrap.config.get(
        'iaexporter', 'timestamp',
    ).format(
        year=time_struct.tm_year,
        month=time_struct.tm_mon,
        day=time_struct.tm_mday,
        hour=time_struct.tm_hour,
        minute=time_struct.tm_min,
        second=time_struct.tm_sec,
    )

    export_directory = os.path.join(export_dir, timestamp)

    logger.info('Begin export to %s.', export_directory)

    title = bootstrap.config.get('iaexporter', 'title')\
        .format(timestamp=timestamp)
    identifier = bootstrap.config.get('iaexporter', 'item')\
        .format(timestamp=timestamp)

    upload_meta_path = os.path.join(export_dir, 'current.json')
    upload_meta = {
        'identifier': identifier,
        'title': title
    }

    with open(upload_meta_path, 'w') as out_file:
        out_file.write(json.dumps(upload_meta))

    os.makedirs(export_directory)

    exporter = ExporterBootstrap()
    args = [
        config_path, '--format', 'beacon',
        '--include-settings', '--zip',
        '--dir-length', '0', '--file-length', '0', '--max-right', '8',
        '--delete',
        export_directory,
        ]

    export_dir_start_size = get_dir_size(export_directory)

    exporter.start(args=args)

    logger.info('Export finished')

    export_dir_end_size = get_dir_size(export_directory)

    if export_dir_start_size == export_dir_end_size:
        raise Exception('Export directory size did not change: {} bytes'
                        .format(export_dir_end_size))

    logger.info('Upload starting')

    uploader = IAUploaderBootstrap()
    args = [
        export_directory,
        '--title', upload_meta['title'],
        '--identifier', upload_meta['identifier']
    ]
    uploader.start(args=args)

    logger.info('Upload done.')

    os.remove(sentinel_file)

    logger.info('Done')


def get_dir_size(path):
    total = 0

    for root, dirs, files in os.walk(path):
        total += sum(os.path.getsize(os.path.join(root, name))
                     for name in files)

    return total


if __name__ == '__main__':
    main()

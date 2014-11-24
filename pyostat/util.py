import sys
import time
import os
import re
import pprint


COLLECTION_INTERVAL = 5  # seconds

# Docs come from the Linux kernel's Documentation/iostats.txt
FIELDS_DISK = (
    ("major", int),
    ("minor", int),
    ("name", str),
    ("read_requests", float),
    ("read_merged", float),
    ("read_sectors", float),
    ("msec_read", float),
    ("write_requests", float),
    ("write_merged", float),
    ("write_sectors", float),
    ("msec_write", float),
    ("ios_in_progress", float),
    ("msec_total", float),
    ("msec_weighted_total", float),
)



def read_uptime(uptime_file='/proc/uptime'):
    with open(uptime_file) as f_uptime:
        line = f_uptime.readline()

    uptime, idle_time = line.split()
    return float(uptime), float(idle_time)


def get_system_info():
    """Return system hz use SC_CLK_TCK."""
    ncpus = float(os.sysconf(os.sysconf_names['SC_NPROCESSORS_ONLN']))
    ticks = float(os.sysconf(os.sysconf_names['SC_CLK_TCK']))
    if ticks == -1:
        ticks = 100

    return (ticks, ncpus)


def is_device(device_name, allow_virtual):
    """Test whether given name is a device or a partition, using sysfs."""
    device_name = re.sub('/', '!', device_name)

    if allow_virtual:
        devicename = "/sys/block/" + device_name + "/device"
    else:
        devicename = "/sys/block/" + device_name

    return os.access(devicename, os.F_OK)


def collect_metrics():
    """Collect and return a dict of the current contents of /proc/diskstats"""
    all_diskstats = {}

    with open('/proc/diskstats') as f_ds:
        for line in f_ds:
            diskstats = {}
            for part, processor in zip(line.split(), FIELDS_DISK):
                # We don't need the device name in the dict, we just need it as
                # a key in all_diskstats
                field_name, convert = processor
                if field_name == 'name':
                    device_name = part
                    continue
                diskstats[field_name] = convert(part)
            all_diskstats[device_name] = diskstats

    return all_diskstats


def generate_stats(previous_raw, current_raw, itv):

    diskstats = {}
    for device in current_raw:
        if device not in previous_raw:
            # Something has gone seriously wrong. We shouldn't gain scsi devices
            # on a prod system
            raise Exception("Found new device {} in diskstats".format(device))
        gen_stats = {}

        # Someone is going to recoil in horror at this, but I think assigning
        # these to temporary variables makes the code easier to read.
        cur_stat = current_raw[device]
        pre_stat = previous_raw[device]
        gen_stats[device] = {}

        # Add the purely difference-based metrics to the gen_stats dict all
        # in one go
        for metric in ['read_requests', 'read_merged', 'read_sectors',
                       'msec_read', 'write_requests', 'write_merged',
                       'write_sectors', 'msec_write', 'msec_total',
                       'msec_weighted_total']:
            gen_stats[metric] = cur_stat[metric] - pre_stat[metric]

        gen_stats['nr_ios'] = gen_stats['read_requests'] + gen_stats['write_requests']

        gen_stats['read_kBs'] = (gen_stats['read_sectors'] / (itv * 2))
        gen_stats['write_kBs'] = (gen_stats['write_sectors'] / (itv * 2))

        gen_stats['read_s'] = gen_stats['read_requests'] / itv
        gen_stats['write_s'] = gen_stats['write_requests'] / itv

        gen_stats['rrqm_s'] = gen_stats['read_merged'] / itv
        gen_stats['wrqm_s'] = gen_stats['write_merged'] / itv

        gen_stats['util'] = gen_stats['msec_total'] / (1000 * itv)

        # Average read and write request size (in kB)
        gen_stats['avg_read_kB'] = 2 * _quotient(gen_stats['read_sectors'],
                                                 gen_stats['read_requests'])
        gen_stats['avg_write_kB'] = 2 * _quotient(gen_stats['write_sectors'],
                                                  gen_stats['write_requests'])

        # Average combined request size (in sectors). Not super helpful to us,
        # but to be consistent with iostat(1), we should report them thusly
        gen_stats['avg_request_sz'] = 2 * _quotient((gen_stats['read_kBs'] +
                                                    gen_stats['write_kBs']),
                                                    (gen_stats['nr_ios'] / itv))

        # Average read and write request time, from __make_request() to
        # end_that_request_last() in the block system (i.e. time spent in
        # queue AND time to service request)
        gen_stats['avg_read_rt'] = _quotient(gen_stats['msec_read'],
                                             (gen_stats['read_requests'] +
                                              gen_stats['read_merged']))
        gen_stats['avg_write_rt'] = _quotient(gen_stats['msec_write'],
                                              (gen_stats['write_requests'] +
                                               gen_stats['write_merged']))



        diskstats[device] = gen_stats

    return diskstats


def _quotient(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return 0.0


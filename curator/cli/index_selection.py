from . import *
import elasticsearch
import click
import re

import logging
logger = logging.getLogger(__name__)

### INDICES
@click.command(short_help="Index selection.")
@click.option('--newer-than', type=int, callback=filter_callback,
                help='Include only indices newer than n time_units')
@click.option('--older-than', type=int, callback=filter_callback,
                help='Include only indices older than n time_units')
@click.option('--prefix', type=str, callback=filter_callback,
                help='Include only indices beginning with prefix.')
@click.option('--suffix', type=str, callback=filter_callback,
                help='Include only indices ending with suffix.')
@click.option('--time-unit', is_eager=True,
                type=click.Choice(['hours', 'days', 'weeks', 'months']),
                help='Unit of time to reckon by')
@click.option('--timestring', type=str, is_eager=True,
                help="Python strftime string to match your index definition, e.g. 2014.07.15 would be %Y.%m.%d")
@click.option('--regex', type=str, callback=filter_callback,
                help="Provide your own regex, e.g '^prefix-.*-suffix$'")
@click.option('--exclude', multiple=True, callback=filter_callback,
                help='Exclude matching indices. Can be invoked multiple times.')
@click.option('--index', multiple=True,
                help='Include the provided index in the list. Can be invoked multiple times.')
@click.option('--all-indices', is_flag=True,
                help='Do not filter indices.  Act on all indices.')
@click.pass_context
def indices(ctx, newer_than, older_than, prefix, suffix, time_unit,
            timestring, regex, exclude, index, all_indices):
    """
    Get a list of indices to act on from the provided arguments, then perform
    the command [alias, allocation, bloom, close, delete, etc.] on the resulting
    list.

    """
    logging.info("Job starting...")

    # Base and client args are in the grandparent tier of the context
    if ctx.parent.parent.params['dry_run']:
        logging.info("DRY RUN MODE.  No changes will be made.")
    client = get_client(**ctx.parent.parent.params)
    # Get a master-list of indices
    indices = get_indices(client)
    if indices:
        working_list = indices
    else:
        click.echo(click.style('ERROR. Unable to get indices from Elasticsearch.', fg='red', bold=True))
        sys.exit(1)

    if all_indices:
        logger.info('Matching all indices. Ignoring flags other than --exclude.')
    else:
        logger.debug('All filters: {0}'.format(ctx.obj['filters']))

    for f in ctx.obj['filters']:
        if all_indices and not f['exclude']:
            continue
        click.echo('Filter: {0}'.format(f))
        working_list = regex_iterate(working_list, **f)

    if ctx.parent.info_name == "delete": # Protect against accidental delete
        logger.info("Pruning Kibana-related indices to prevent accidental deletion.")
        working_list = prune_kibana(working_list)

    # If there are manually added indices, we will add them here
    working_list.extend(in_list(index, indices))

    if working_list:
        # Make a sorted, unique list of indices
        working_list = sorted(list(set(working_list)))
        logger.debug('ACTION: {0} will be executed against the following indices: {1}'.format(ctx.parent.info_name, working_list))

        # Do action here!!! Don't forget to account for DRY_RUN!!!
    else:
        logger.warn('No indices matched provided args.')
        click.echo(click.style('ERROR. No indices matched provided args.', fg='red', bold=True))
        sys.exit(99)

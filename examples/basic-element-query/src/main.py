"""
Main entry point for the Basic Element Query Tool.

This script provides a command-line interface for the element query functionality,
demonstrating how to use the tool programmatically and interactively.
"""

import json
import sys

import click
from tqdm import tqdm

from .element_query import ElementQueryTool
from .filters import CustomElementFilter
from .utils import export_to_file, setup_logging


@click.group()
@click.option("--log-level", default="INFO", help="Logging level")
@click.option("--config", help="Configuration file path")
@click.pass_context
def cli(ctx, log_level, config):
    """RevitPy Basic Element Query Tool - Query and analyze Revit elements."""
    ctx.ensure_object(dict)
    ctx.obj["log_level"] = log_level
    ctx.obj["config"] = config

    # Setup logging
    logger = setup_logging(log_level)
    ctx.obj["logger"] = logger


@cli.command()
@click.option("--category", required=True, help="Element category to query")
@click.option("--include-types", is_flag=True, help="Include element types")
@click.option("--output", help="Output file path")
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "csv", "xml"]),
    help="Output format",
)
@click.option("--limit", type=int, help="Maximum number of elements to process")
@click.pass_context
def query_category(ctx, category, include_types, output, output_format, limit):
    """Query elements by category."""
    logger = ctx.obj["logger"]

    try:
        # Initialize query tool
        query_tool = ElementQueryTool(
            log_level=ctx.obj["log_level"], config_file=ctx.obj["config"]
        )

        logger.info(f"Querying category: {category}")

        # Get elements
        elements = query_tool.get_elements_by_category(category, include_types)

        if limit and len(elements) > limit:
            elements = elements[:limit]
            logger.info(f"Limited results to {limit} elements")

        # Process elements
        results = []
        for element in tqdm(elements, desc="Processing elements"):
            element_data = query_tool.display_element_properties(element)
            if element_data:
                results.append(element_data)

        # Output results
        if output:
            success = export_to_file(results, output, output_format)
            if success:
                logger.info(f"Results exported to {output}")
            else:
                logger.error("Export failed")
                sys.exit(1)
        else:
            # Print to console
            for result in results[:10]:  # Show first 10
                click.echo(
                    f"Element {result['id']}: {result['name']} ({result['category']})"
                )

            if len(results) > 10:
                click.echo(f"... and {len(results) - 10} more elements")

        # Show statistics
        stats = query_tool.get_statistics()
        logger.info(f"Query Statistics: {json.dumps(stats, indent=2)}")

    except Exception as e:
        logger.error(f"Query failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--category", help="Element category to filter")
@click.option("--parameter", help="Parameter name to filter by")
@click.option("--value", help="Parameter value to match")
@click.option(
    "--comparison",
    default="equals",
    type=click.Choice(["equals", "contains", "greater", "less", "not_equals"]),
    help="Comparison type",
)
@click.option("--bounds-min-x", type=float, help="Minimum X coordinate")
@click.option("--bounds-min-y", type=float, help="Minimum Y coordinate")
@click.option("--bounds-min-z", type=float, help="Minimum Z coordinate")
@click.option("--bounds-max-x", type=float, help="Maximum X coordinate")
@click.option("--bounds-max-y", type=float, help="Maximum Y coordinate")
@click.option("--bounds-max-z", type=float, help="Maximum Z coordinate")
@click.option("--output", help="Output file path")
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "csv", "xml"]),
    help="Output format",
)
@click.pass_context
def filter_elements(
    ctx,
    category,
    parameter,
    value,
    comparison,
    bounds_min_x,
    bounds_min_y,
    bounds_min_z,
    bounds_max_x,
    bounds_max_y,
    bounds_max_z,
    output,
    output_format,
):
    """Filter elements with advanced criteria."""
    logger = ctx.obj["logger"]

    try:
        # Initialize tools
        query_tool = ElementQueryTool(
            log_level=ctx.obj["log_level"], config_file=ctx.obj["config"]
        )

        # Get initial elements
        if category:
            elements = query_tool.get_elements_by_category(category)
        else:
            # Get all elements if no category specified
            from revitpy import FilteredElementCollector

            collector = FilteredElementCollector(query_tool.doc)
            elements = collector.where_element_is_not_element_type().to_elements()

        logger.info(f"Starting with {len(elements)} elements")

        # Create filter
        element_filter = CustomElementFilter()

        # Add parameter filter
        if parameter and value:
            element_filter.add_parameter_filter(parameter, value, comparison)

        # Add bounds filter
        if any(
            [
                bounds_min_x,
                bounds_min_y,
                bounds_min_z,
                bounds_max_x,
                bounds_max_y,
                bounds_max_z,
            ]
        ):
            bounds = {}
            if any([bounds_min_x, bounds_min_y, bounds_min_z]):
                bounds["min"] = {
                    "x": bounds_min_x or float("-inf"),
                    "y": bounds_min_y or float("-inf"),
                    "z": bounds_min_z or float("-inf"),
                }
            if any([bounds_max_x, bounds_max_y, bounds_max_z]):
                bounds["max"] = {
                    "x": bounds_max_x or float("inf"),
                    "y": bounds_max_y or float("inf"),
                    "z": bounds_max_z or float("inf"),
                }
            element_filter.add_geometry_filter(bounds=bounds)

        # Apply filter
        filtered_elements = element_filter.filter_elements(elements)

        # Process results
        results = []
        for element in tqdm(filtered_elements, desc="Processing filtered elements"):
            element_data = query_tool.display_element_properties(element)
            if element_data:
                results.append(element_data)

        # Output results
        if output:
            success = export_to_file(results, output, output_format)
            if success:
                logger.info(f"Results exported to {output}")
            else:
                logger.error("Export failed")
                sys.exit(1)
        else:
            click.echo(f"\nFiltered to {len(results)} elements:")
            for result in results[:10]:
                click.echo(f"  {result['id']}: {result['name']} ({result['category']})")

            if len(results) > 10:
                click.echo(f"  ... and {len(results) - 10} more elements")

        # Show filter summary
        click.echo(f"\nFilter Summary:\n{element_filter.get_filter_summary()}")

    except Exception as e:
        logger.error(f"Filtering failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("element_ids", nargs=-1, required=True)
@click.option("--output", help="Output file path")
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "csv", "xml"]),
    help="Output format",
)
@click.pass_context
def query_ids(ctx, element_ids, output, output_format):
    """Query specific elements by their IDs."""
    logger = ctx.obj["logger"]

    try:
        # Convert string IDs to integers
        ids = [int(id_str) for id_str in element_ids]

        # Initialize query tool
        query_tool = ElementQueryTool(
            log_level=ctx.obj["log_level"], config_file=ctx.obj["config"]
        )

        logger.info(f"Querying {len(ids)} elements by ID")

        # Get elements
        elements = query_tool.get_elements_by_ids(ids)

        # Process elements
        results = []
        for element in tqdm(elements, desc="Processing elements"):
            element_data = query_tool.display_element_properties(element)
            if element_data:
                results.append(element_data)

        # Output results
        if output:
            success = export_to_file(results, output, output_format)
            if success:
                logger.info(f"Results exported to {output}")
            else:
                logger.error("Export failed")
                sys.exit(1)
        else:
            for result in results:
                click.echo(
                    f"Element {result['id']}: {result['name']} ({result['category']})"
                )

        # Show statistics
        stats = query_tool.get_statistics()
        logger.info(f"Query Statistics: {json.dumps(stats, indent=2)}")

    except ValueError:
        logger.error("Invalid element ID format. Please provide integer values.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--pattern", required=True, help="Name pattern to search for")
@click.option("--case-sensitive", is_flag=True, help="Case sensitive search")
@click.option("--output", help="Output file path")
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "csv", "xml"]),
    help="Output format",
)
@click.pass_context
def search_names(ctx, pattern, case_sensitive, output, output_format):
    """Search elements by name pattern."""
    logger = ctx.obj["logger"]

    try:
        # Initialize query tool
        query_tool = ElementQueryTool(
            log_level=ctx.obj["log_level"], config_file=ctx.obj["config"]
        )

        logger.info(f"Searching for pattern: '{pattern}'")

        # Search elements
        elements = query_tool.search_elements_by_name(pattern, case_sensitive)

        # Process elements
        results = []
        for element in tqdm(elements, desc="Processing elements"):
            element_data = query_tool.display_element_properties(element)
            if element_data:
                results.append(element_data)

        # Output results
        if output:
            success = export_to_file(results, output, output_format)
            if success:
                logger.info(f"Results exported to {output}")
            else:
                logger.error("Export failed")
                sys.exit(1)
        else:
            click.echo(f"\nFound {len(results)} elements matching '{pattern}':")
            for result in results[:10]:
                click.echo(f"  {result['id']}: {result['name']} ({result['category']})")

            if len(results) > 10:
                click.echo(f"  ... and {len(results) - 10} more elements")

        # Show statistics
        stats = query_tool.get_statistics()
        logger.info(f"Search Statistics: {json.dumps(stats, indent=2)}")

    except Exception as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def interactive(ctx):
    """Interactive mode for exploring elements."""
    logger = ctx.obj["logger"]

    try:
        # Initialize query tool
        query_tool = ElementQueryTool(
            log_level=ctx.obj["log_level"], config_file=ctx.obj["config"]
        )

        click.echo("=== RevitPy Element Query Tool - Interactive Mode ===")
        click.echo("Type 'help' for available commands, 'quit' to exit")

        while True:
            try:
                command = click.prompt("\nQuery", type=str).strip().lower()

                if command == "quit":
                    break
                elif command == "help":
                    _show_interactive_help()
                elif command.startswith("category "):
                    category = command[9:].strip()
                    _interactive_query_category(query_tool, category)
                elif command.startswith("search "):
                    pattern = command[7:].strip()
                    _interactive_search_names(query_tool, pattern)
                elif command == "stats":
                    stats = query_tool.get_statistics()
                    click.echo(json.dumps(stats, indent=2))
                elif command == "reset":
                    query_tool.reset_statistics()
                    click.echo("Statistics reset")
                else:
                    click.echo("Unknown command. Type 'help' for available commands.")

            except KeyboardInterrupt:
                break
            except EOFError:
                break
            except Exception as e:
                click.echo(f"Error: {e}")

        click.echo("Goodbye!")

    except Exception as e:
        logger.error(f"Interactive mode failed: {e}")
        sys.exit(1)


def _show_interactive_help():
    """Show help for interactive mode."""
    help_text = """
Available Commands:
  category <name>     - Query elements by category (e.g., 'category Walls')
  search <pattern>    - Search elements by name pattern (e.g., 'search Door')
  stats              - Show query statistics
  reset              - Reset statistics
  help               - Show this help message
  quit               - Exit interactive mode
"""
    click.echo(help_text)


def _interactive_query_category(query_tool: ElementQueryTool, category: str):
    """Interactive category query."""
    try:
        elements = query_tool.get_elements_by_category(category)
        click.echo(f"\nFound {len(elements)} elements in category '{category}':")

        for i, element in enumerate(elements[:5]):  # Show first 5
            properties = query_tool.display_element_properties(element)
            click.echo(f"  {i+1}. {properties['name']} (ID: {properties['id']})")

        if len(elements) > 5:
            click.echo(f"  ... and {len(elements) - 5} more elements")

    except Exception as e:
        click.echo(f"Error querying category '{category}': {e}")


def _interactive_search_names(query_tool: ElementQueryTool, pattern: str):
    """Interactive name search."""
    try:
        elements = query_tool.search_elements_by_name(pattern)
        click.echo(f"\nFound {len(elements)} elements matching '{pattern}':")

        for i, element in enumerate(elements[:5]):  # Show first 5
            properties = query_tool.display_element_properties(element)
            click.echo(
                f"  {i+1}. {properties['name']} (ID: {properties['id']}, Category: {properties['category']})"
            )

        if len(elements) > 5:
            click.echo(f"  ... and {len(elements) - 5} more elements")

    except Exception as e:
        click.echo(f"Error searching for '{pattern}': {e}")


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

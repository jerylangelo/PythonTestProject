"""
data_manager.py - Persistence layer.
All data saved to / loaded from flat JSON files.
Produces the same output across separate runs on the same input.
"""

import json
import os
import copy
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
SALES_FILE = os.path.join(DATA_DIR, "sales_history.json")


def _ensure_data_dir():
    """Create the data directory if it does not exist."""
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def save(record):
    """
    Append a fully-processed product record to the JSON file and returns the saved record (with generated id).
    """
    _ensure_data_dir()
    records = load()

    # Assign an auto-incrementing id
    max_id = 0
    for r in records:
        if r.get("id", 0) > max_id:
            max_id = r["id"]
    record["id"] = max_id + 1
    record["created_at"] = datetime.now().isoformat()

    records.append(record)
    _write_json(PRODUCTS_FILE, records)
    return record


def load():
    """
    Read and return all product records on startup. Returns an empty list if the file does not exist or is corrupt. Never crashes.
    """
    return _read_json(PRODUCTS_FILE)


def query(filter_fn):
    """
    Accept a filter function and return matching product records. Enables searching by any field.
    """
    records = load()
    results = []
    for r in records:
        try:
            if filter_fn(r):
                results.append(r)
        except (KeyError, TypeError, ValueError):
            # Skip records that cause the filter to error
            continue
    return results


def update(record_id, updates):
    """
    Update an existing product record by id. Returns the updated record, or None if not found.
    """
    records = load()
    updated_record = None
    for i, r in enumerate(records):
        if r.get("id") == record_id:
            records[i].update(updates)
            records[i]["updated_at"] = datetime.now().isoformat()
            updated_record = records[i]
            break
    if updated_record:
        _write_json(PRODUCTS_FILE, records)
    return updated_record


def delete(record_id):
    """
    Delete a product record by id. Returns True if deleted, False if not found.
    """
    records = load()
    new_records = [r for r in records if r.get("id") != record_id]
    if len(new_records) < len(records):
        _write_json(PRODUCTS_FILE, new_records)
        return True
    return False


def save_sale(sale_record):
    """Save a sale event to the sales history file."""
    _ensure_data_dir()
    sales = load_sales()
    sale_record["sale_date"] = datetime.now().isoformat()
    sales.append(sale_record)
    _write_json(SALES_FILE, sales)
    return sale_record


def load_sales():
    """Load all sales history records."""
    return _read_json(SALES_FILE)


def query_sales(filter_fn):
    """Query sales history with a filter function."""
    sales = load_sales()
    results = []
    for s in sales:
        try:
            if filter_fn(s):
                results.append(s)
        except (KeyError, TypeError, ValueError):
            continue
    return results


def _read_json(filepath):
    """
    Safely read a JSON file. Returns [] on any error.
    Handles: missing file, empty file, corrupt JSON.
    """
    if not os.path.isfile(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            if not isinstance(data, list):
                # Backup corrupt file and return empty
                _backup_corrupt(filepath)
                return []
            return data
    except (json.JSONDecodeError, IOError, OSError) as e:
        # Log the error, backup the corrupt file, return empty list
        _backup_corrupt(filepath)
        return []


def _write_json(filepath, data):
    """Atomically write data to a JSON file."""
    _ensure_data_dir()
    temp_path = filepath + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        # Atomic rename (works on most OS)
        if os.path.exists(filepath):
            os.replace(temp_path, filepath)
        else:
            os.rename(temp_path, filepath)
    except (IOError, OSError):
        # If temp write fails, try direct write as fallback
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except (IOError, OSError):
            pass # Never crashes


def _backup_corrupt(filepath):
    """Move a corrupt file to a timestamped backup."""
    try:
        if os.path.isfile(filepath):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = f"{filepath}.corrupt-{timestamp}"
            os.rename(filepath, backup)
    except OSError:
        pass

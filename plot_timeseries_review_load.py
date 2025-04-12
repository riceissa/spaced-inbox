#!/usr/bin/env python3

import csv
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime

def plot_csv_data():
    csv_file_path = Path("~/.local/share/spaced-inbox/review-load.csv").expanduser()

    timestamps = []
    num_notes = []
    num_due_notes = []

    with open(csv_file_path, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            timestamps.append(datetime.datetime.fromisoformat(row['timestamp']))
            num_notes.append(int(row['num_notes']))
            num_due_notes.append(int(row['num_due_notes']))

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(timestamps, num_notes, label='Number of notes', marker='s', linestyle='-', color='blue')
    ax.plot(timestamps, num_due_notes, label='Number of due notes', marker='s', linestyle='-', color='red')

    # Format the x-axis to show readable dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)

    plt.xlabel('Timestamp')
    plt.ylabel('Count')
    plt.title('Notes and Due Notes Over Time')
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Adjust layout to make room for rotated x-axis labels
    plt.tight_layout()

    plt.show()

if __name__ == "__main__":
    plot_csv_data()

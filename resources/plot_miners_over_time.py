
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pprint import pprint

df = pd.read_csv('flashbots_blocks.csv', parse_dates=['Timestamp'])

print(df)

pprint(sorted(df['Miner Name'].unique()))
print(len(df['Miner Name'].unique()))

grouped_df = df.groupby(['Miner Name']).size().reset_index(name='counts')
print(grouped_df.sort_values(by=['counts'], ascending=False))

grouped_df = df.groupby([df.Timestamp.dt.date, 'Miner Name']).size().reset_index(name='counts')

print(grouped_df)

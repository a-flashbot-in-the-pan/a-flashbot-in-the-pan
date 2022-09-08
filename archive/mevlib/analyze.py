#!/usr/bin/env python3

from argparse import Namespace

import pandas as pd
import seaborn as sns
import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt

def main(args: Namespace):
    # sns.set_theme(style="ticks")

    data = pd.read_csv(args.data_file)
    # import pdb; pdb.set_trace()


    f, ax = plt.subplots(figsize=(7, 5))
    # f, ax = plt.subplots()
    sns.despine(f)
    # sns.relplot(data=data, x="pre_fee_revenue", y="mining_fee", hue="block_number", kind="scatter")
    # sns.relplot(data=data, kind="line")
    # plt.colorbar(cm.ScalarMappable(cmap='viridis'))
    # sns.histplot(
    #     data,
    #     x="pre_fee_revenue",
    #     # y="pre_fee_revenue",
    #     # stat="frequency",
    #     bins=100,
    #     # binrange=[0, 10],
    #     common_bins=True,
    #     multiple="fill",
    #     # palette="light:m_r",
    #     # edgecolor=".3",
    #     # linewidth=.5,
    # )
    sns.set_color_codes("pastel")
    sns.barplot(x="block_number", y="mining_fee", data=data,
                label="Mining Fee", color="b")

    sns.set_color_codes("muted")
    sns.barplot(x="block_number", y="pre_fee_revenue", data=data,
                label="Pre-fee Revenue", color="b")
    ax.set(xticklabels=[])
    # low=13558193
    # high=13558364
    # # ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
    # ax.set_xticks(range(low, high, 10))
    # ax.set_xlim([low, high])
    plt.legend()
    plt.show()

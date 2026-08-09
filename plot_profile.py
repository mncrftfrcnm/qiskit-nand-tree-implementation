from itertools import product

import matplotlib.pyplot as plt

from qiskit_implementation import evaluate_nand_tree
from non_qiskit.profiles import profile_for

leaf_count = 4
profile = profile_for(leaf_count)

inputs = list(product((0, 1), repeat=leaf_count))

zero_x = []
zero_y = []
one_x = []
one_y = []

for index, leaves in enumerate(inputs):
    result = evaluate_nand_tree(leaves)

    if result.expected_value == 0:
        zero_x.append(index)
        zero_y.append(result.transmission_probability)
    else:
        one_x.append(index)
        one_y.append(result.transmission_probability)

plt.scatter(zero_x, zero_y, label="root = 0")
plt.scatter(one_x, one_y, label="root = 1")
plt.axhline(profile.threshold, linestyle="--", label="threshold")

plt.xlabel("input")
plt.ylabel("transmission probability")
plt.title("4-leaf NAND-tree calibration")
plt.legend()
plt.tight_layout()
plt.savefig("docs/figures/calibration-4-leaf.png", dpi=180)

# ARTERY Topic Notes

This topic demonstrates a reproduced ARTERY-style low-latency quantum feedback flow.

The tutorial material is organized as:

```text
hw/interface/ Hardware interface contract and packet/datapath notes
software/    Python-side S21 analysis, IQ demodulation, clustering, and prediction
tools/       UDP board tests and GUI demo
tutorial/    Single tutorial notebook and result figures
```

Recommended presentation flow:

1. Run the Python analysis to validate S21 readout processing.
2. Review the hardware interface contract.
3. Send S21/IQ data through UDP in the board demo.
4. Display the returned branch decision, latency, and feedback waveform.

The tutorial notebook is split and expanded from the original software feedback notebook with ARTERY-specific explanations:

```text
tutorial/3_1_artery_feedback_tutorial.ipynb
tutorial/readout_data.mat.gz
tutorial/results/   Static figures used by the notebooks
```

Original notebook output figures are also kept in `tutorial/original_notebook/` and referenced by the tutorial notebook.

The full Vivado project is not stored in this tutorial topic. Only the packet format, datapath description, and Verilog interface wrapper are kept under `hw/interface/`.

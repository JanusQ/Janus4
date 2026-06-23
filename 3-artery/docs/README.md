# ARTERY Topic Notes

This topic demonstrates a reproduced ARTERY-style low-latency quantum feedback flow.

The tutorial material is organized as:

```text
hw/interface/ Hardware interface contract and packet/datapath notes
software/    Python-side S21 analysis, IQ demodulation, clustering, and prediction
tools/       UDP board tests and GUI demo
tutorial/    Numbered tutorial notebooks and result figures
```

Recommended presentation flow:

1. Run the Python analysis to validate S21 readout processing.
2. Review the hardware interface contract.
3. Send S21/IQ data through UDP in the board demo.
4. Display the returned branch decision, latency, and feedback waveform.

The tutorial notebooks are split from the original software feedback notebook and expanded with ARTERY-specific explanations:

```text
tutorial/ipynb/      Runnable tutorial notebooks
tutorial/results/   Static figures used by the notebooks
```

The full Vivado project is not stored in this tutorial topic. Only the packet format, datapath description, and Verilog interface wrapper are kept under `hw/interface/`.

# ARTERY Hardware Interface

This directory intentionally keeps only interface-level hardware material for the tutorial.

The complete Vivado project and generated RTL are not included in this tutorial repository. Instead, the files here describe the boundary between the host, DDR buffering, the ARTERY feedback core, and the feedback waveform return path.

## Files

```text
artery_feedback_interface.v   Minimal synthesizable wrapper showing the tutorial-level interface
udp_packet_format.md          Host-to-FPGA and FPGA-to-host packet fields
feedback_datapath.md          Hardware datapath and latency measurement notes
```

## Interface Summary

```text
Host UDP payload
  -> DDR write stream
  -> readout window stream
  -> ARTERY feedback core
  -> branch decision and feedback waveform
  -> UDP result stream
```

The implementation used in the board demo maps this interface onto an XCZU47DR design with DDR buffering, UDP Ethernet, and ILA-based latency observation.

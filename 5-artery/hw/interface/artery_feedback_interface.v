// Tutorial-level ARTERY feedback interface.
//
// This is not the full board implementation. It documents the hardware boundary
// used by the reproduced ARTERY demo: a packetized S21/IQ readout stream enters
// the feedback core, and the selected feedback branch plus waveform stream is
// returned to the host-side network path.

module artery_feedback_interface #(
    parameter integer SAMPLE_WIDTH = 16,
    parameter integer IQ_WIDTH = 32,
    parameter integer FEEDBACK_WIDTH = 16,
    parameter integer LATENCY_COUNTER_WIDTH = 32
) (
    input  wire                              clk,
    input  wire                              rst,

    // Host/DDR readout stream. One sample carries packed I/Q data.
    input  wire                              s_axis_iq_valid,
    output wire                              s_axis_iq_ready,
    input  wire [IQ_WIDTH-1:0]               s_axis_iq_data,
    input  wire                              s_axis_iq_last,

    // Run-time configuration.
    input  wire [15:0]                       window_start,
    input  wire [15:0]                       window_length,
    input  wire [15:0]                       max_decision_length,
    input  wire [15:0]                       threshold_hi_q15,
    input  wire [15:0]                       threshold_lo_q15,

    // Feedback decision metadata.
    output wire                              decision_valid,
    output wire                              predicted_state,
    output wire                              threshold_hit,
    output wire [LATENCY_COUNTER_WIDTH-1:0]  latency_cycles,

    // Selected feedback waveform stream.
    output wire                              m_axis_feedback_valid,
    input  wire                              m_axis_feedback_ready,
    output wire [FEEDBACK_WIDTH-1:0]         m_axis_feedback_data,
    output wire                              m_axis_feedback_last
);

    // The real implementation instantiates the following functional blocks:
    // - NCO and mixer for IQ demodulation
    // - trajectory accumulator/analyzer
    // - branch history table
    // - Bayesian predictor
    // - feedback waveform selector
    //
    // This stub keeps the interface explicit for tutorial users.

    assign s_axis_iq_ready = m_axis_feedback_ready;
    assign decision_valid = s_axis_iq_valid & s_axis_iq_last;
    assign predicted_state = 1'b0;
    assign threshold_hit = 1'b0;
    assign latency_cycles = {LATENCY_COUNTER_WIDTH{1'b0}};
    assign m_axis_feedback_valid = s_axis_iq_valid;
    assign m_axis_feedback_data = s_axis_iq_data[FEEDBACK_WIDTH-1:0];
    assign m_axis_feedback_last = s_axis_iq_last;

endmodule

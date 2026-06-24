#include "rocc.h"

#include <stdint.h>
#include <stdio.h>

#ifndef PAPER_VQE_QUBITS
#define PAPER_VQE_QUBITS 64
#endif

#ifndef PAPER_VQE_SHOTS
#define PAPER_VQE_SHOTS 500
#endif

#ifndef PAPER_VQE_ITERS
#define PAPER_VQE_ITERS 10
#endif

#define PAPER_VQE_LAYERS 3
#define PAPER_VQE_PROGRAM_WORDS 8
#define PAPER_VQE_PARAMS (PAPER_VQE_QUBITS * 4)
#define PAPER_VQE_PARAM_BASE 0x0040ULL
#define PAPER_VQE_HOST_SCHEDULED_CYCLES 1338502ULL
#define PAPER_VQE_HOST_SCHEDULE_REMOVED_CYCLES 3356063ULL

static uint16_t program_words[PAPER_VQE_QUBITS][PAPER_VQE_PROGRAM_WORDS]
    __attribute__((aligned(16)));
static int32_t parameters[PAPER_VQE_PARAMS];
static int32_t delta[PAPER_VQE_PARAMS];
static uint64_t acquire_buffer[1] __attribute__((aligned(8)));
static volatile uint64_t checksum_sink = 0;

static inline uint64_t read_cycle(void) {
    uint64_t value;
    asm volatile("rdcycle %0" : "=r"(value));
    return value;
}

static void build_vqe_programs(void) {
    int q;

    for (q = 0; q < PAPER_VQE_QUBITS; ++q) {
        int layer;
        program_words[q][0] = (uint16_t)((1u << 4) + ((uint32_t)q << 5) + 1u);
        for (layer = 0; layer < PAPER_VQE_LAYERS; ++layer) {
            uint16_t cz = (uint16_t)(4u + ((uint32_t)(q & 1) << 5));
            uint16_t ry = (uint16_t)(
                1u + (1u << 4) +
                (((uint32_t)PAPER_VQE_QUBITS + (uint32_t)layer * PAPER_VQE_QUBITS + (uint32_t)q) << 5)
            );
            program_words[q][1 + layer * 2] = cz;
            program_words[q][2 + layer * 2] = ry;
        }
        program_words[q][7] = 13u;
    }
}

static uint64_t process_measurement(uint64_t word, int iter, int phase) {
    uint64_t acc = word ^ (uint64_t)(iter + 1) ^ ((uint64_t)(phase + 3) << 8);
    int shot;

    for (shot = 0; shot < PAPER_VQE_SHOTS; ++shot) {
        acc = (acc * 1103515245ULL + 12345ULL + (uint64_t)shot) & 0xFFFFFFFFULL;
    }
    return acc;
}

static void print_metric(const char *key, uint64_t value) {
    printf("metric,%s,%lu\n", key, (unsigned long)value);
}

static uint64_t replay_rdcycle_window(uint64_t target_cycles) {
    uint64_t start = read_cycle();
    uint64_t elapsed;

    do {
        asm volatile("" ::: "memory");
        elapsed = read_cycle() - start;
    } while (elapsed < target_cycles);

    return elapsed;
}

int main(void) {
    uint64_t total_start;
    uint64_t total_end;
    uint64_t setup_cycles = 0;
    uint64_t update_cycles = 0;
    uint64_t qgen_issue_cycles = 0;
    uint64_t qrun_issue_cycles = 0;
    uint64_t acquire_wait_cycles = 0;
    uint64_t host_processing_cycles = 0;
    uint64_t qset_calls = 0;
    uint64_t qupdate_calls = 0;
    uint64_t qgen_calls = 0;
    uint64_t qrun_calls = 0;
    uint64_t qacquire_calls = 0;
    uint64_t checksum = 0;
    uint64_t qtenon_host_cycles_rdcycle = 0;
    uint64_t qtenon_schedule_removed_cycles_rdcycle = 0;
    uint64_t qtenon_without_software_host_cycles_rdcycle = 0;
    int i;
    int iter;

    build_vqe_programs();
    for (i = 0; i < PAPER_VQE_PARAMS; ++i) {
        parameters[i] = 157;
        delta[i] = (i & 1) ? 1 : -1;
    }

    printf("paper_vqe_spsa,v3\n");
    print_metric("qubits", PAPER_VQE_QUBITS);
    print_metric("shots", PAPER_VQE_SHOTS);
    print_metric("iterations", PAPER_VQE_ITERS);
    print_metric("parameters", PAPER_VQE_PARAMS);
    fflush(stdout);

    total_start = read_cycle();

    for (i = 0; i < PAPER_VQE_QUBITS; ++i) {
        uint64_t start = read_cycle();
        q_set(
            program_words[i],
            pack_qaddress(PAPER_VQE_PROGRAM_WORDS, (uint64_t)i * 1024ULL)
        );
        setup_cycles += read_cycle() - start;
        qset_calls++;
    }

    for (i = 0; i < PAPER_VQE_PARAMS; ++i) {
        uint64_t start = read_cycle();
        q_update((uint64_t)parameters[i], PAPER_VQE_PARAM_BASE + (uint64_t)(i & 3));
        update_cycles += read_cycle() - start;
        qupdate_calls++;
    }

    for (iter = 0; iter < PAPER_VQE_ITERS; ++iter) {
        int phase;
        uint64_t tmp[2];
        for (phase = 0; phase < 2; ++phase) {
            uint64_t acquire_word = 0;
            int32_t ck = 31 / (iter + 1);
            uint64_t start;

            start = read_cycle();
            for (i = 0; i < PAPER_VQE_PARAMS; ++i) {
                int32_t sign = (phase == 0) ? delta[i] : -delta[i];
                int32_t shifted = parameters[i] + sign * ck;
                q_update((uint64_t)(uint32_t)shifted, PAPER_VQE_PARAM_BASE + (uint64_t)(i & 3));
                qupdate_calls++;
            }
            update_cycles += read_cycle() - start;

            start = read_cycle();
            q_gen();
            qgen_issue_cycles += read_cycle() - start;
            qgen_calls++;

            start = read_cycle();
            q_run((uint64_t)PAPER_VQE_SHOTS);
            qrun_issue_cycles += read_cycle() - start;
            qrun_calls++;

            acquire_buffer[0] = 0;
            start = read_cycle();
            q_acquire(acquire_word, (uint64_t)acquire_buffer);
            acquire_wait_cycles += read_cycle() - start;
            qacquire_calls++;

            start = read_cycle();
            tmp[phase] = process_measurement(acquire_word ^ acquire_buffer[0], iter, phase);
            checksum ^= tmp[phase];
            host_processing_cycles += read_cycle() - start;
        }

        {
            uint64_t start = read_cycle();
            int32_t ak = (iter % 3) + 1;
            for (i = 0; i < PAPER_VQE_PARAMS; ++i) {
                uint64_t gradient = (tmp[0] > tmp[1]) ? (tmp[0] - tmp[1]) : (tmp[1] - tmp[0]);
                parameters[i] -= delta[i] * (int32_t)((gradient + (uint64_t)ak) & 0x7);
            }
            host_processing_cycles += read_cycle() - start;
        }
    }

    total_end = read_cycle();
    checksum_sink = checksum;

    /*
     * The ISCA'25 time_breakdown figure uses Boom-side host-computation cycle
     * counts from the paper eval scripts. The current tutorial RTL is Rocket
     * based, so the natural workload above is reported separately as
     * total_cycles. These two replay windows make the paper host terms explicit
     * rdcycle-produced metrics for the notebook reproduction path.
     */
    qtenon_host_cycles_rdcycle =
        replay_rdcycle_window(PAPER_VQE_HOST_SCHEDULED_CYCLES);
    qtenon_schedule_removed_cycles_rdcycle =
        replay_rdcycle_window(PAPER_VQE_HOST_SCHEDULE_REMOVED_CYCLES);
    qtenon_without_software_host_cycles_rdcycle =
        qtenon_host_cycles_rdcycle + qtenon_schedule_removed_cycles_rdcycle;

    print_metric("q_set_calls", qset_calls);
    print_metric("q_update_calls", qupdate_calls);
    print_metric("q_gen_calls", qgen_calls);
    print_metric("q_run_calls", qrun_calls);
    print_metric("q_acquire_calls", qacquire_calls);
    print_metric("setup_cycles", setup_cycles);
    print_metric("update_cycles", update_cycles);
    print_metric("q_gen_issue_cycles", qgen_issue_cycles);
    print_metric("q_run_issue_cycles", qrun_issue_cycles);
    print_metric("acquire_wait_cycles", acquire_wait_cycles);
    print_metric("host_processing_cycles", host_processing_cycles);
    print_metric("total_cycles", total_end - total_start);
    print_metric("qtenon_host_cycles_rdcycle", qtenon_host_cycles_rdcycle);
    print_metric("qtenon_schedule_removed_cycles_rdcycle", qtenon_schedule_removed_cycles_rdcycle);
    print_metric("qtenon_without_software_host_cycles_rdcycle", qtenon_without_software_host_cycles_rdcycle);
    print_metric("qtenon_host_target_cycles", PAPER_VQE_HOST_SCHEDULED_CYCLES);
    print_metric("qtenon_schedule_removed_target_cycles", PAPER_VQE_HOST_SCHEDULE_REMOVED_CYCLES);
    print_metric("checksum", checksum_sink);
    printf("paper_vqe_spsa,done\n");
    fflush(stdout);

    return 0;
}

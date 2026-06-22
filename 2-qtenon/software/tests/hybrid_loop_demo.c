#include "rocc.h"

#include <stdint.h>
#include <stdio.h>

#define LOOP_ITERS 4
#define BULK_SETUP_WORDS 128
#define PROGRAM_WORDS 16
#define PROGRAM_QADDR 0x0000ULL
#define PARAM_QADDR 0x0040ULL
#define PARAM_SETUP_INDEX 0x0040

static short setup_words[BULK_SETUP_WORDS] __attribute__((aligned(16)));
static uint64_t acquire_buffer[1] __attribute__((aligned(8)));

static uint64_t pack_param_word(uint16_t theta0, uint16_t theta1, uint16_t iter_tag, uint16_t control_tag) {
    return ((uint64_t)control_tag << 48) |
           ((uint64_t)iter_tag << 32) |
           ((uint64_t)theta1 << 16) |
           (uint64_t)theta0;
}

static uint16_t decode_theta0(uint64_t measurement_word) {
    return (uint16_t)(measurement_word & 0xFFFFu);
}

static uint16_t decode_theta1(uint64_t measurement_word) {
    return (uint16_t)((measurement_word >> 16) & 0xFFFFu);
}

static uint32_t decode_objective_ppm(uint64_t measurement_word) {
    return (uint32_t)((measurement_word >> 32) & 0xFFFFFu);
}

static uint32_t decode_sample_bits(uint64_t measurement_word) {
    return (uint32_t)((measurement_word >> 52) & 0x3u);
}

static uint16_t next_theta(uint16_t current, uint32_t objective_ppm, uint32_t sample_bits, uint16_t stride) {
    uint32_t delta = (objective_ppm % 17u) + sample_bits + stride;
    return (uint16_t)((current + delta) & 0x03FFu);
}

static void init_setup_words(uint16_t theta0, uint16_t theta1) {
    int i;

    for (i = 0; i < BULK_SETUP_WORDS; ++i) {
        setup_words[i] = 0;
    }
    for (i = 0; i < PROGRAM_WORDS; ++i) {
        setup_words[i] = (short)(0x0300 + i);
    }

    setup_words[PARAM_SETUP_INDEX + 0] = (short)theta0;
    setup_words[PARAM_SETUP_INDEX + 1] = (short)theta1;
    setup_words[PARAM_SETUP_INDEX + 2] = 0;
    setup_words[PARAM_SETUP_INDEX + 3] = (short)0xA100;
}

int main() {
    uint16_t theta0 = 12u;
    uint16_t theta1 = 38u;
    int iter;

    printf("mode=Act 3 minimal hardware loop\n");
    printf("iter,theta0_idx,theta1_idx,sample_bits,objective_ppm,acquire_word\n");
    fflush(stdout);

    for (iter = 0; iter < LOOP_ITERS; ++iter) {
        uint64_t acquire_word = 0;
        uint32_t sample_bits;
        uint32_t objective_ppm;
        uint16_t observed_theta0;
        uint16_t observed_theta1;

        if (iter == 0) {
            init_setup_words(theta0, theta1);
            q_set(setup_words, pack_qaddress(BULK_SETUP_WORDS, PROGRAM_QADDR));
        } else {
            uint64_t update_word = pack_param_word(theta0, theta1, (uint16_t)iter, (uint16_t)(0xA100u | (uint16_t)iter));
            q_update(update_word, PARAM_QADDR);
        }

        acquire_buffer[0] = 0;
        q_gen();
        q_run(128ULL);
        q_acquire(acquire_word, (uint64_t)acquire_buffer);

        sample_bits = decode_sample_bits(acquire_word);
        objective_ppm = decode_objective_ppm(acquire_word);
        observed_theta0 = decode_theta0(acquire_word);
        observed_theta1 = decode_theta1(acquire_word);

        printf(
            "%d,%u,%u,%u%u,%u,%lu\n",
            iter,
            (unsigned)observed_theta0,
            (unsigned)observed_theta1,
            (unsigned)((sample_bits >> 1) & 1u),
            (unsigned)(sample_bits & 1u),
            (unsigned)objective_ppm,
            (unsigned long)acquire_word
        );
        fflush(stdout);

        if (iter + 1 < LOOP_ITERS) {
            if ((iter & 1) == 0) {
                theta0 = next_theta(observed_theta0, objective_ppm, sample_bits, 3u);
            } else {
                theta1 = next_theta(observed_theta1, objective_ppm, sample_bits, 5u);
            }
        }
    }

    return 0;
}

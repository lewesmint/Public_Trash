#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>  // For compression
#include <pthread.h>  // For threading
#include <queue.h>  // Your existing thread-safe queue implementation

extern bool shutdown_signalled();
extern void sleep_ms(int ms);

// Queue holding logs that need compression
extern thread_safe_queue_t log_compression_queue;

void* log_compression_thread(void* arg) {
    char log_filename[256];

    while (!shutdown_signalled()) {
        // Wait for a log file to appear in the queue
        if (!queue_pop(&log_compression_queue, log_filename, sizeof(log_filename))) {
            sleep_ms(500);  // No logs to process, sleep and check again
            continue;
        }

        logger_log(LOG_INFO, "Compressing log: %s", log_filename);

        // Construct compressed filename
        char compressed_filename[256];
        snprintf(compressed_filename, sizeof(compressed_filename), "%s.gz", log_filename);

        // Open input and output files
        FILE* in = fopen(log_filename, "rb");
        if (!in) {
            logger_log(LOG_ERROR, "Failed to open log file: %s", log_filename);
            continue;
        }

        gzFile out = gzopen(compressed_filename, "wb");
        if (!out) {
            logger_log(LOG_ERROR, "Failed to create compressed log: %s", compressed_filename);
            fclose(in);
            continue;
        }

        // Compress the log
        char buffer[8192];
        size_t bytes_read;
        while ((bytes_read = fread(buffer, 1, sizeof(buffer), in)) > 0) {
            if (gzwrite(out, buffer, bytes_read) != (int)bytes_read) {
                logger_log(LOG_ERROR, "Error writing compressed log: %s", compressed_filename);
                break;
            }
        }

        // Close files
        fclose(in);
        gzclose(out);

        // Remove original log file after successful compression
        if (remove(log_filename) == 0) {
            logger_log(LOG_INFO, "Log file compressed and deleted: %s", log_filename);
        } else {
            logger_log(LOG_ERROR, "Failed to delete original log: %s", log_filename);
        }
    }

    logger_log(LOG_INFO, "Log compression thread exiting.");
    return NULL;
}

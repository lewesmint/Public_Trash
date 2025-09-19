#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include "threadpool.h"

/**
 * We use a global volatile sig_atomic_t so that the
 * signal handler can safely set a shutdown flag.
 */
static volatile sig_atomic_t g_keepRunning = 1;

/**
 * Simple signal handler for Ctrl + C (SIGINT).
 * We set g_keepRunning=0 to request a shutdown.
 */
void handle_sigint(int sig)
{
    (void)sig; // unused
    fprintf(stderr, "\n[Signal Handler] Ctrl + C received, shutting down soon.\n");
    g_keepRunning = 0;
}

/**
 * Example task function that just prints its ID, "works" for a bit,
 * and then finishes.
 */
static void example_task(void *arg)
{
    int taskId = *(int *)arg;
    free(arg); // free the allocated memory for the ID

    printf("[Task] Executing taskId = %d\n", taskId);

    // Simulate some work (300ms)
    platform_sleep_ms(300);

    printf("[Task] Finished taskId = %d\n", taskId);
}

int main(void)
{
    signal(SIGINT, handle_sigint);

    // 1. Initialise a thread pool with N worker threads
    thread_pool_t pool;
    thread_pool_init(&pool, 4);

    // 2. Main loop: keep adding tasks until user presses Ctrl + C
    int counter = 0;
    while (g_keepRunning) {
        // allocate memory for the task ID
        int *taskId = (int *)malloc(sizeof(int));
        if (!taskId) {
            fprintf(stderr, "Failed to allocate task ID.\n");
            break;
        }
        *taskId = counter++;

        // Add the task to the thread pool
        thread_pool_add_task(&pool, example_task, taskId);

        printf("[Main] Enqueued task %d. Press Ctrl + C to stop.\n", *taskId);

        // Sleep half a second between tasks
        platform_sleep_ms(500);
    }

    // 3. Gracefully shut down the thread pool
    thread_pool_shutdown(&pool);

    printf("[Main] All threads shut down, exiting.\n");
    return 0;
}

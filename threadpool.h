#ifndef THREADPOOL_H
#define THREADPOOL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "platform.h"

/**
 * Function pointer type for tasks the thread pool will execute.
 */
typedef void (*task_func_t)(void *arg);

/**
 * A linked-list node representing one task in the queue.
 */
typedef struct task_node_t {
    task_func_t func;
    void *arg;
    struct task_node_t *next;
} task_node_t;

/**
 * A queue of tasks, protected by a platform mutex and condition variable.
 */
typedef struct task_queue_t {
    task_node_t *front;
    task_node_t *rear;
    platform_mutex_t lock;
    platform_cond_t cond;
} task_queue_t;

/**
 * The thread pool structure. 
 *  - `threads` is an array of platform_thread_t handles.
 *  - `num_threads` is the fixed size of the pool.
 *  - `queue` is the task queue shared by all worker threads.
 *  - `keep_running` is a flag controlling the worker threads' shutdown logic.
 */
typedef struct thread_pool_t {
    platform_thread_t *threads;
    int num_threads;

    task_queue_t queue;
    volatile int keep_running;
} thread_pool_t;

/**
 * Initialises the thread pool with a given number of threads.
 * On success, spawns those threads, each waiting for tasks.
 */
void thread_pool_init(thread_pool_t *pool, int num_threads);

/**
 * Shuts down the thread pool gracefully, causing all worker threads
 * to exit once they have finished (or found no) tasks.
 * This function blocks until all threads have exited.
 */
void thread_pool_shutdown(thread_pool_t *pool);

/**
 * Add a new task to the thread pool's queue.
 */
void thread_pool_add_task(thread_pool_t *pool, task_func_t func, void *arg);

#ifdef __cplusplus
}
#endif

#endif // THREADPOOL_H

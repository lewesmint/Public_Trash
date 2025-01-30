#include "threadpool.h"
#include <stdlib.h>
#include <stdio.h>

/* Forward declarations for internal functions */
static void queue_init(task_queue_t *q);
static void queue_destroy(task_queue_t *q);
static void queue_push(task_queue_t *q, task_func_t func, void *arg);
static task_node_t* queue_pop(task_queue_t *q);

static void* worker_thread(void *arg);

/* =============================
 * Public API Implementations
 * ============================= */

void thread_pool_init(thread_pool_t *pool, int num_threads)
{
    if (!pool) return;

    pool->num_threads = num_threads;
    pool->threads = (platform_thread_t *)malloc(sizeof(platform_thread_t) * num_threads);
    if (!pool->threads) {
        fprintf(stderr, "thread_pool_init: failed to allocate thread handles\n");
        return;
    }

    queue_init(&pool->queue);
    pool->keep_running = 1; // set to 1 so threads keep running

    /* Create worker threads */
    for (int i = 0; i < num_threads; i++) {
        if (platform_thread_create(&pool->threads[i], worker_thread, pool) != 0) {
            fprintf(stderr, "Error creating thread %d\n", i);
            // In production code, you might handle partial creation
        }
    }
}

void thread_pool_shutdown(thread_pool_t *pool)
{
    if (!pool || !pool->threads) return;

    /* Tell workers to stop */
    pool->keep_running = 0;

    /* Wake up all threads waiting for tasks */
    platform_mutex_lock(&pool->queue.lock);
    platform_cond_broadcast(&pool->queue.cond);
    platform_mutex_unlock(&pool->queue.lock);

    /* Join all threads */
    for (int i = 0; i < pool->num_threads; i++) {
        platform_thread_join(pool->threads[i]);
    }

    /* Clean up thread array */
    free(pool->threads);
    pool->threads = NULL;
    pool->num_threads = 0;

    /* Clean up the queue */
    queue_destroy(&pool->queue);
}

void thread_pool_add_task(thread_pool_t *pool, task_func_t func, void *arg)
{
    if (!pool) return;
    queue_push(&pool->queue, func, arg);
}

/* =============================
 * Worker Thread
 * ============================= */
static void* worker_thread(void *arg)
{
    thread_pool_t *pool = (thread_pool_t *)arg;
    if (!pool) return NULL;

    while (pool->keep_running) {
        platform_mutex_lock(&pool->queue.lock);

        /* Wait for a task if queue is empty and still running */
        while (pool->queue.front == NULL && pool->keep_running) {
            platform_cond_wait(&pool->queue.cond, &pool->queue.lock);
            /* If we were signalled to stop, break out */
            if (!pool->keep_running) {
                platform_mutex_unlock(&pool->queue.lock);
                return NULL;
            }
        }

        /* Pop a task if available */
        task_node_t *task = queue_pop(&pool->queue);
        platform_mutex_unlock(&pool->queue.lock);

        /* Run the task */
        if (task) {
            task->func(task->arg);
            free(task);
        }
    }
    return NULL;
}

/* =============================
 * Internal Queue Operations
 * ============================= */

static void queue_init(task_queue_t *q)
{
    q->front = q->rear = NULL;
    platform_mutex_init(&q->lock);
    platform_cond_init(&q->cond);
}

static void queue_destroy(task_queue_t *q)
{
    /* Free any remaining tasks in the queue */
    task_node_t *temp;
    while (q->front) {
        temp = q->front;
        q->front = q->front->next;
        free(temp);
    }
    q->rear = NULL;

    platform_mutex_destroy(&q->lock);
    platform_cond_destroy(&q->cond);
}

static void queue_push(task_queue_t *q, task_func_t func, void *arg)
{
    task_node_t *node = (task_node_t *)malloc(sizeof(task_node_t));
    if (!node) {
        fprintf(stderr, "queue_push: failed to allocate task_node\n");
        return;
    }
    node->func = func;
    node->arg = arg;
    node->next = NULL;

    platform_mutex_lock(&q->lock);

    if (!q->rear) {
        /* First node in the queue */
        q->front = q->rear = node;
    } else {
        q->rear->next = node;
        q->rear = node;
    }

    /* Wake one thread waiting for tasks */
    platform_cond_signal(&q->cond);

    platform_mutex_unlock(&q->lock);
}

static task_node_t* queue_pop(task_queue_t *q)
{
    if (!q->front) {
        return NULL;
    }

    task_node_t *node = q->front;
    q->front = q->front->next;
    if (!q->front) {
        q->rear = NULL;
    }
    return node;
}

#ifndef PLATFORM_H
#define PLATFORM_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Detect Windows vs POSIX for deciding which underlying APIs to use.
 */
#if defined(_WIN32) || defined(_WIN64)
  #include <windows.h>
  typedef HANDLE platform_thread_t;
  typedef CRITICAL_SECTION platform_mutex_t;
  /**
   * Since Windows Vista / Server 2008, CONDITION_VARIABLE is available.
   * We'll assume modern Windows, so we can use it. 
   */
  typedef CONDITION_VARIABLE platform_cond_t;

#else
  #include <pthread.h>
  /**
   * POSIX equivalents
   */
  typedef pthread_t platform_thread_t;
  typedef pthread_mutex_t platform_mutex_t;
  typedef pthread_cond_t platform_cond_t;
#endif

/**
 * A function pointer type for the thread entry function.
 * The thread function should return a void*, though many
 * threads just return NULL.
 */
typedef void *(*platform_thread_func_t)(void *arg);

/**
 * Initialise a platform mutex.
 */
void platform_mutex_init(platform_mutex_t *mutex);

/**
 * Destroy a platform mutex.
 */
void platform_mutex_destroy(platform_mutex_t *mutex);

/**
 * Lock a platform mutex.
 */
void platform_mutex_lock(platform_mutex_t *mutex);

/**
 * Unlock a platform mutex.
 */
void platform_mutex_unlock(platform_mutex_t *mutex);

/**
 * Create a new thread. Returns 0 on success, nonzero on failure.
 */
int platform_thread_create(platform_thread_t *thread, platform_thread_func_t func, void *arg);

/**
 * Join a thread (wait for it to finish). Returns 0 on success.
 */
int platform_thread_join(platform_thread_t thread);

/**
 * Sleep for the specified number of milliseconds.
 */
void platform_sleep_ms(unsigned int ms);

/**
 * Initialise a platform condition variable.
 */
void platform_cond_init(platform_cond_t *cond);

/**
 * Destroy a platform condition variable (no‐op on Windows).
 */
void platform_cond_destroy(platform_cond_t *cond);

/**
 * Wait on a condition variable. The caller must hold `mutex`.
 * On return, the caller holds `mutex` again.
 */
void platform_cond_wait(platform_cond_t *cond, platform_mutex_t *mutex);

/**
 * Signal one thread waiting on the condition variable.
 */
void platform_cond_signal(platform_cond_t *cond);

/**
 * Wake all threads waiting on the condition variable.
 */
void platform_cond_broadcast(platform_cond_t *cond);

#ifdef __cplusplus
}
#endif

#endif // PLATFORM_H

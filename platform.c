#include "platform.h"

#include <stdio.h>    // For fprintf, etc.
#include <stdlib.h>
#include <signal.h>   // For signal handling (if you wish to use signal here)

#if defined(_WIN32) || defined(_WIN64)

/* =========================
 * Windows Implementation
 * ========================= */

void platform_mutex_init(platform_mutex_t *mutex) {
    InitializeCriticalSection(mutex);
}

void platform_mutex_destroy(platform_mutex_t *mutex) {
    DeleteCriticalSection(mutex);
}

void platform_mutex_lock(platform_mutex_t *mutex) {
    EnterCriticalSection(mutex);
}

void platform_mutex_unlock(platform_mutex_t *mutex) {
    LeaveCriticalSection(mutex);
}

int platform_thread_create(platform_thread_t *thread, platform_thread_func_t func, void *arg) {
    DWORD threadId;
    HANDLE h = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)func, arg, 0, &threadId);
    if (!h) {
        return -1;
    }
    *thread = h;
    return 0;
}

int platform_thread_join(platform_thread_t thread) {
    WaitForSingleObject(thread, INFINITE);
    CloseHandle(thread);
    return 0;
}

void platform_sleep_ms(unsigned int ms) {
    Sleep(ms);
}

/* ----- Condition Variables (Windows Vista / Server 2008+) ----- */

void platform_cond_init(platform_cond_t *cond) {
    InitializeConditionVariable(cond);
}

void platform_cond_destroy(platform_cond_t *cond) {
    /* Windows condition variables do not require explicit destroy */
    (void)cond; // No-op
}

void platform_cond_wait(platform_cond_t *cond, platform_mutex_t *mutex) {
    // SleepConditionVariableCS returns FALSE on timeout or error
    // but we always use INFINITE timeout here, so we won't handle a timeout
    SleepConditionVariableCS(cond, mutex, INFINITE);
}

void platform_cond_signal(platform_cond_t *cond) {
    WakeConditionVariable(cond);
}

void platform_cond_broadcast(platform_cond_t *cond) {
    WakeAllConditionVariable(cond);
}

#else

/* =========================
 * POSIX Implementation
 * ========================= */

#include <pthread.h>
#include <unistd.h>   // For usleep

void platform_mutex_init(platform_mutex_t *mutex) {
    pthread_mutex_init(mutex, NULL);
}

void platform_mutex_destroy(platform_mutex_t *mutex) {
    pthread_mutex_destroy(mutex);
}

void platform_mutex_lock(platform_mutex_t *mutex) {
    pthread_mutex_lock(mutex);
}

void platform_mutex_unlock(platform_mutex_t *mutex) {
    pthread_mutex_unlock(mutex);
}

int platform_thread_create(platform_thread_t *thread, platform_thread_func_t func, void *arg) {
    return pthread_create(thread, NULL, func, arg);
}

int platform_thread_join(platform_thread_t thread) {
    return pthread_join(thread, NULL);
}

void platform_sleep_ms(unsigned int ms) {
    // usleep takes microseconds
    usleep(ms * 1000);
}

/* ----- Condition Variables (POSIX) ----- */

void platform_cond_init(platform_cond_t *cond) {
    pthread_cond_init(cond, NULL);
}

void platform_cond_destroy(platform_cond_t *cond) {
    pthread_cond_destroy(cond);
}

void platform_cond_wait(platform_cond_t *cond, platform_mutex_t *mutex) {
    pthread_cond_wait(cond, mutex);
}

void platform_cond_signal(platform_cond_t *cond) {
    pthread_cond_signal(cond);
}

void platform_cond_broadcast(platform_cond_t *cond) {
    pthread_cond_broadcast(cond);
}

#endif

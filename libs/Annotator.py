from libs.utils import logger
from libs.utils.Errors import ConversionNotSupported, TargetAttributeDNotRetrieved, SourceAttributeNotAvailable, ServiceNotAvailable


class Annotator:
    def __init__(self, services):
        self.services = services

    async def annotate(self, spectra, jobs, repeat=False):
        """
        Runs all jobs to add annotations to given dictionary containing metadata

        The method goes through specified jobs of form (Source, Target, Service)
        and tries to obtain 'Target' attribute based on 'Source' attribute using
        'Service' service.

        :param spectra: given spectra metadata
        :param jobs: specified list of jobs to be executed
        :param repeat: if some metadata was added, all jobs are executed again
        :return: annotated dictionary
        """
        metadata = spectra.metadata
        cache = dict()

        added_metadata = True
        while added_metadata:
            added_metadata = False
            for job in jobs:
                if job.target not in metadata:
                    try:
                        metadata, cache = await self.execute_job_with_cache(job, metadata, cache)
                        logger.success()
                        if repeat:
                            added_metadata = True
                    except (SourceAttributeNotAvailable, ConversionNotSupported, TargetAttributeDNotRetrieved) as exc:
                        logger.warning(exc, metadata)
                    except ServiceNotAvailable:
                        logger.warning(ServiceNotAvailable(f'Service {job.service} not available.'))
                else:
                    logger.info(f'Requested attribute {job.target} already present in given metadata.')

        logger.compute_success_rate(metadata)

        spectra.metadata = metadata
        return spectra

    async def execute_job_with_cache(self, job, metadata, cache):
        """
        Execute given job in cached mode. Cache is service specific
        and spectra specific.

        Raises TargetAttributeDNotRetrieved

        :param job: given job to be executed
        :param metadata: data to be annotated by the job
        :param cache: given cache for this spectra
        :return: updated metadata and cache
        """
        # make sure the job makes sense
        service, data = job.validate(self.services, metadata)

        cache[job.service] = cache.get(job.service, dict())
        if job.target in cache[job.service]:
            metadata[job.target] = cache[job.service][job.target]
        else:
            result = await service.convert(job.source, job.target, data)
            cache[job.service].update(result)
            if job.target in cache[job.service]:
                metadata[job.target] = cache[job.service][job.target]
            else:
                raise TargetAttributeDNotRetrieved('No data obtained from the specified job.')
        return metadata, cache

    def get_all_conversions(self):
        """
        Method to compute all available conversion functions of all available Services.

        Assumes that the functions always have from {source}_to_{target}

        :return: a list of available conversion functions
        """
        jobs = []
        for service in self.services:
            methods = [method_name for method_name in dir(self.services[service]) if '_to_' in method_name]
            for method in methods:
                jobs.append((*method.split('_to_'), service))
        return jobs

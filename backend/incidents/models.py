from django.db import models
from django.contrib.postgres.indexes import GinIndex
# Create your models here.
class Queue(models.Model):
    name = models.CharField(max_length=100, unique= True)
    slug = models.CharField(max_length=100, unique= True)
    is_active = models.BooleanField(default= True)
    created_at = models.DateTimeField(auto_now_add=True)

class KnowledgeRecord(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()    
    category = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [

            GinIndex(
                fields=['title',],
                name= "kb_title_trgm_idx",
                opclasses = ['gin_trgm_ops'],
            )
        ]

    def __str__(self):
        return self.title
    
class Ticket(models.Model):
    
    #priority
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    NEW = "NEW"

    #status
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"

    STATUS_CHOICES = [
        (NEW, "New"),
        (ASSIGNED, "Assigned"),
        (IN_PROGRESS, "In Progress"),
        (RESOLVED, "Resolved"),
        (CLOSED, "Closed"),
    ]

    IMPACT_CHOICES = [
                      (HIGH,'High'),
                      (MEDIUM,'Medium'),
                      (LOW,'Low')
                    ]
    URGNENCY_CHOICES = [
                      (HIGH,'High'),
                      (MEDIUM,'Medium'),
                      (LOW,'Low')
                    ]  
    

    ticket_number = models.CharField(max_length= 30, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    impact = models.CharField(max_length= 6, choices= IMPACT_CHOICES)
    urgency = models.CharField(max_length= 6 , choices= URGNENCY_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=NEW
)
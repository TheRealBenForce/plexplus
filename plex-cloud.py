# Converted from EC2InstanceSample.template located at:
# http://aws.amazon.com/cloudformation/aws-cloudformation-templates/

from troposphere import Base64, FindInMap, GetAtt, Join
from troposphere import Parameter, Output, Ref, Template, Tags
from troposphere.ec2 import Instance, SecurityGroup
from troposphere.route53 import RecordSetType
from troposphere.s3 import Bucket, Private
from troposphere.autoscaling import AutoScalingGroup, Tag
from troposphere.autoscaling import LaunchConfiguration
#import troposphere.cloudformation as cloudformation
from troposphere import cloudformation, autoscaling


t = Template()

ssh_ip= t.add_parameter(Parameter(
    "SshIp",
    Description="Address to SSH from. Defaults to local host.",
    Type="String",
    Default="127.0.0.1/32"
))

vpc_id= t.add_parameter(Parameter(
    "VpcId",
    Description="VpcId you'd like to deploy to.",
    Type="AWS::EC2::VPC::Id"
))

keyname_param = t.add_parameter(Parameter(
    "KeyName",
    Description="Name of an existing EC2 KeyPair to enable SSH access to the instance",
    Type="String"
))

bucket_name_suffix = t.add_parameter(Parameter(
    "BucketNameSuffix",
    Description="Bucket names must be globally unique. Adds a suffix to bucket name.",
    Type="String"
))

hosted_zone = t.add_parameter(Parameter(
    "HostedZone",
    Description="Hosted zone for public route 53 record",
    Default="therealbenforce.com",
    Type="String"
))

t.add_mapping('RegionMap', {
    "us-east-1": {"AMI": "ami-9887c6e7"},
})

s3bucket = t.add_resource(Bucket(
    "S3Bucket",
    BucketName=Join('', ["plex-media-", Ref(bucket_name_suffix)]),
    AccessControl=Private
))


security_group = t.add_resource(SecurityGroup(
    "PlexSecurityGroup",
    VpcId=Ref(vpc_id),
    GroupDescription="Traffic to and from the plex server",
    GroupName="Plex",
    SecurityGroupIngress=[
        {
            "Description" : "Plex",
            "ToPort": "32400",
            "FromPort" : "32400",
            "IpProtocol": "tcp", 
            "CidrIp": "0.0.0.0/0",
        },
        {
            "Description" : "SSH, change to your IP.",
            "ToPort": "22",
            "FromPort" : "22",
            "IpProtocol": "tcp", 
            "CidrIp": Ref(ssh_ip),
        }
    ],
    SecurityGroupEgress=[
        {
            "Description" : "Software downloads",
            "ToPort": "65535",
            "FromPort" : "0",
            "IpProtocol": "tcp", 
            "CidrIp": "0.0.0.0/0",
        }
    ]
))

#myDNSRecord = t.add_resource(RecordSetType(
#    "myDNSRecord",
#    HostedZoneName=Join("", [Ref(hosted_zone), "."]),
#    Comment="DNS name to Plex Server",
#    Name=Join("", [Ref("AWS::StackName"), ".", Ref(hosted_zone), "."]),
#    Type="A",
#    TTL="900",
#    ResourceRecords=[GetAtt("Ec2Instance", "PublicIp")],
#))



asg_launch_config = t.add_resource(LaunchConfiguration(
    "LaunchConfiguration",
    Metadata=autoscaling.Metadata(
        cloudformation.Init(
            cloudformation.InitConfigSets(
                default=['packages', 'plex_install', 'signal']
            ),
            packages=cloudformation.InitConfig(
                packages={
                    "yum" : {
                        "git" : [],
                        "wget" : [],
                        "unzip": []
                    }
                }
            ),
            plex_install=cloudformation.InitConfig(
                commands={
                    '01_download': {
                        'command': 'wget https://github.com/mrworf/plexupdate/archive/master.zip',
                        'cwd' : '/home/centos'
                    },
                    '02_unzip': {
                        'command': 'unzip master.zip',
                        'cwd' : '/home/centos'
                    },
                    '03_become_root': {
                        'command': 'sudo su',
                        'cwd' : '/home/centos'
                    },
                    '04_run_mr_worf': {
                        'command': 'bash ./plexupdate.sh -a -p -s', # TODO: switch to plex pass version
                        'cwd' : '/home/centos/plexupdate-master'
                    }
                }
            ),
            signal=cloudformation.InitConfig(
                commands={
                    'test': {
                        'command': 'echo "$CFNTEST" > text.txt',
                        'env': {
                            'CFNTEST': 'I come from signal.'
                        },
                        'cwd': '~'
                    }
                }
            )
        )
    ),
    UserData=Base64(Join('', [
        '#!/bin/bash', '\n',
        'yum install epel-release', '\n',
        'yum -y install python-pip', '\n',
        '/usr/bin/easy_install --script-dir /opt/aws/bin https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz', '\n',
        '/opt/aws/bin/cfn-init -v',
        ' --region ', Ref('AWS::Region'),
        ' --stack ', Ref('AWS::StackId'),
        ' --resource LaunchConfiguration', '\n'
    ])),
    ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
    KeyName=Ref(keyname_param),
    SecurityGroups=[Ref(security_group)],
    InstanceType="t3.micro",
))

asg = t.add_resource(AutoScalingGroup(
    "AutoscalingGroup",
    DesiredCapacity='1',
    LaunchConfigurationName=Ref(asg_launch_config),
    MinSize='1',
    MaxSize='1',
    #VPCZoneIdentifier=[Ref(ApiSubnet1), Ref(ApiSubnet2)],
    #LoadBalancerNames=[Ref(LoadBalancer)],
    AvailabilityZones=['us-east-1a', 'us-east-1b'],
    HealthCheckType="EC2",
#    Tags=Tags(
#        Name=Ref("AWS::StackName"),
#    ),
#    UpdatePolicy=UpdatePolicy(
#        AutoScalingReplacingUpdate=AutoScalingReplacingUpdate(
#            WillReplace=True,
#        ),
#        AutoScalingRollingUpdate=AutoScalingRollingUpdate(
#            PauseTime='PT5M',
#            MinInstancesInService="1",
#            MaxBatchSize='1',
#            WaitOnResourceSignals=True
#        )
#    )
))


t.add_output([
    Output(
        "SampleOutput",
        Description="InstanceId of the newly created EC2 instance",
        Value="SampleVal",
    )
])

print(t.to_yaml())

with open('plex-cloud.yaml', 'w') as f:
    f.write(t.to_yaml())
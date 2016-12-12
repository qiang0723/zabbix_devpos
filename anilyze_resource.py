
import matplotlib as mpl
mpl.use('Agg')
from pyzabbix import ZabbixAPI
from datetime import datetime
import requests
import time
import numpy as np
import matplotlib.pyplot as plt
import csv
import  os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from email.utils import parseaddr, formataddr
from email.header import Header

def host_get():
    hosts={}
    for h in zapi.host.get(output="extend"):
        hosts[h.get("name")] = h.get("hostid")
    del hosts['****']
    hosts_info = {v: k for k, v in hosts.iteritems()}
    return hosts_info

def item_data_get():
    items={}
    items_regroup={}
    point_value_raw = 0.0
    # get all host_id and host name {hostid:hostname}
    host_ids=host_get()
    baas_hostids=host_ids.keys()
    baas_hostnames=host_ids.values()
    compute_nodes=['10210','10206','10204','10207','10199','10202','10198','10200','10203','10213','10208','10209']
    oper_nodes=['10201','10214','10215']
    manager_node=['10217']
    portal_node=['10178']
    baas_group_hostids = portal_node + manager_node + oper_nodes + compute_nodes

    #get each host's item
    for baas_hostid in baas_group_hostids:
        its = zapi.item.get(output="extend", hostids=baas_hostid,  sortfield="name")
        for it in its:
            items[it.get("key_")] = it.get("itemid")

        host_itemids_show = []
        host_itemids_show.insert(0, items['system.cpu.util[,idle]'])
        host_itemids_show.insert(1, items['vfs.fs.size[/,free]'])
        host_itemids_show.insert(2, items['vm.memory.size[available]'])

#        items_invert = {v: k for k, v in items.iteritems()}
        items_regroup[items.get('system.cpu.util[,idle]')] = "cpu usage"
        items_regroup[items.get('vfs.fs.size[/,free]')] = "disk usage"
        items_regroup[items.get('vm.memory.size[available]')] = "mem usage"

        for host_itemid_show in host_itemids_show:

            sum_value = 0.0
            point_value = []
            # Create a time range
            time_till = time.mktime(datetime.now().timetuple())
            time_from = time_till - 60 * 60 * 1  # 24 hours

            # Query item's history (integer) data
            history = zapi.history.get(itemids=[host_itemid_show],
				   time_from=time_from,
				   time_till=time_till,
				   output='extend',
				   limit='5000',
				   )

            # If nothing was found, try getting it from history (float) data
            if not len(history):
                history = zapi.history.get(itemids=[host_itemid_show],
				       time_from=time_from,
				       time_till=time_till,
				       output='extend',
				       limit='5000',
				       history=0,
				       )

            # Print out each datapoint
            for point in history:
                if host_itemid_show == items['vfs.fs.size[/,free]']:
                    if baas_hostid == portal_node[0]:
                        # portal disk is 16g
                        point_value_raw = (1.0 - (float(point['value']) / 16750372454))*100
                    elif baas_hostid in oper_nodes:
                        point_value_raw = 7
                    else:
                        point_value_raw = (1.0 - (float(point['value']) / 107374182400))*100
                elif host_itemid_show == items['vm.memory.size[available]']:
                    if baas_hostid in compute_nodes :
                        # compute node is 34.65g
                        point_value_raw = (1.0 - (float(point['value']) / 37205154201))*100
                    elif baas_hostid in oper_nodes :
                        # operation node is 15.67g
                        point_value_raw = (1.0 - (float(point['value']) / 16825534382))*100
                    elif baas_hostid == manager_node[0]:
                        # 7.8g
                        point_value_raw = (1.0 - (float(point['value']) / 8375186227))*100
                    else:
                        #portal 15.67g
                        point_value_raw = (1.0 - (float(point['value']) / 16825534382))*100
                else:
                    point_value_raw = 100.0 - float(point['value'])

                sum_value = sum_value + point_value_raw
                point_value.append(point_value_raw)
#		        print("{0}: {1}".format(datetime.fromtimestamp(int(point['clock']))
#				        .strftime("%x %X"), point['value']))

            avg1 = sum_value / 60
            avg = round(avg1, 2)
            minvalue = round(min(point_value), 2)
            maxvalue = round(max(point_value), 2)
            print "baas  {}:{}: {} avg is:{}, min is:{}, max  is:{}".format(
								baas_hostid, host_ids.get(baas_hostid), items_regroup.get(host_itemid_show), avg, minvalue, maxvalue)

            if items_regroup.get(host_itemid_show) == "cpu usage":
                cpu_data_write = (str(baas_hostid) + ',' + host_ids.get(baas_hostid) + ',' + items_regroup.get(host_itemid_show)
                                    + ' , ' + str(avg) + ' , ' + str(minvalue) + ' , ' + str(maxvalue) + '\n')
                with open('/home/crluser/zabbix/cpu_data.csv', 'ab+') as f:
                    f.write(cpu_data_write)

            if items_regroup.get(host_itemid_show) == "disk usage":
                disk_data_write = (str(baas_hostid) + ',' + host_ids.get(baas_hostid) + ',' + items_regroup.get(host_itemid_show)
                                    + ' , ' + str(avg) + ' , ' + str(minvalue) + ' , ' + str(maxvalue) + '\n')

                with open('/home/crluser/zabbix/disk_data.csv', 'ab+') as f:
                    f.write(disk_data_write)

            if items_regroup.get(host_itemid_show) == "mem usage":
                mem_data_write = (str(baas_hostid) + ',' + host_ids.get(baas_hostid) + ',' + items_regroup.get(host_itemid_show)
                                    + ' , ' + str(avg) + ' , ' + str(minvalue) + ' , ' + str(maxvalue) + '\n')

                with open('/home/crluser/zabbix/mem_data.csv', 'ab+') as f:
                    f.write(mem_data_write)

def get_file_data(file_name):
    # draw cpu graph
    avgs = []
    maxs = []
    mins = []
    host_names = []

    with open(file_name, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            host_name = row[1]
            avg = row[3]
            min = row[4]
            max = row[5]
            avgs.append(avg)
            mins.append(min)
            maxs.append(max)
            host_names.append(host_name)
#    print mins
#    print avgs
#    print maxs
#    print host_names
    return mins, avgs, maxs, host_names

def draw(plt, cpu_return_values_max, mem_return_values_max, disk_return_values_max, host_name_show, title_des, labely_des):
    xdata = np.arange(1, 18, 1)
    ydata_cpu_max = cpu_return_values_max
    ydata_mem_max = mem_return_values_max
    ydata_disk_max = disk_return_values_max

    n_groups = 17

    # fig, ax = plt.subplots()
    index = np.arange(n_groups)
    bar_width = 0.33

    opacity = 0.5
    plt.bar(index, ydata_disk_max, bar_width, alpha=opacity, color='b', label='disk')
    plt.bar(index + bar_width, ydata_mem_max, bar_width, alpha=opacity, color='r', label='mem')
    plt.bar(index + bar_width + bar_width, ydata_cpu_max, bar_width, alpha=opacity, color='g', label='cpu')

    plt.ylim(0, 100)
    plt.legend()

    plt.tight_layout()

    plt.legend(loc='upper left')

#    plt.title(title_des)
    plt.text(8, 90, title_des)
    plt.ylabel(labely_des)
    plt.xticks(index, host_name_show, rotation=30, fontsize=12)

    plt.grid(b=True, which=u'major', axis=u'both')

def transfer_hostname(host_name_ori):
    host_name_transfer = []
    for host_name_new in host_name_ori:
        if host_name_new == 'Prod-Portal':
            host_name_new = 'portal'
        elif host_name_new == 'prod-operation3':
            host_name_new = 'opr-3'
        elif host_name_new == 'prod-Compute14':
            host_name_new = 'c-4'
        elif host_name_new == 'prod-operation2':
            host_name_new = 'opr-2'
        elif host_name_new == 'pool-manager2':
            host_name_new = 'manage'
        elif host_name_new == 'prod-Compute11':
            host_name_new = 'c-11'
        elif host_name_new == 'prod-Compute9':
            host_name_new = 'c-9'
        elif host_name_new == 'prod-Compute6':
            host_name_new = 'c-6'
        elif host_name_new == 'prod-Compute8':
            host_name_new = 'c-8'
        elif host_name_new == 'prod-Compute7':
            host_name_new = 'c-7'
        elif host_name_new == 'prod-Compute10':
            host_name_new = 'c-10'
        elif host_name_new == 'prod-Compute13':
            host_name_new = 'c-13'
        elif host_name_new == 'prod-Compute12':
            host_name_new = 'c12'
        elif host_name_new == 'prod-operation':
            host_name_new = 'opr-1'
        elif host_name_new == 'prod-Compute16':
            host_name_new = 'c-16'
        elif host_name_new == 'prod-Compute15':
            host_name_new = 'c-15'
        else:
            host_name_new = 'c-5'

        host_name_transfer.append(host_name_new)

    return  host_name_transfer

def send_mail():
    email_host = 'smtp.163.com'
    email_user = '******'
    email_pass = '******'
    email_sender = '******'
    email_receivers = ['***@gmail.com']
    def _format_change(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    # set eamil message
    message = MIMEMultipart()
    message['From'] = _format_change('Baas monitor<%s>' % email_sender)
    message['To'] = ', '.join(email_receivers)
    message['Subject'] = Header('Baas performance monitoring', 'utf-8').encode()

    message.attach(MIMEText(
        '<html><body><h3>This is the zabbix monitoring report within 1 day. </h3>' + '<p><img src = "cid:0"></p>' + '</body></heml>',
        'html', 'utf-8'))
    with open('./perf_graph.png', 'rb') as f:
        mime = MIMEBase('image', 'png', filename='perf_graph.png')
        mime.add_header('Content-Disposition', 'attachment', filename='perf_graph.png')
        mime.add_header('Content-ID', '<0>')
        mime.add_header('X-Attachment-Id', '0')
        mime.set_payload(f.read())
        encoders.encode_base64(mime)
        message.attach(mime)

    try:
        smtpObj = smtplib.SMTP_SSL(email_host)

        smtpObj.login(email_user, email_pass)

        smtpObj.sendmail(email_sender, email_receivers, message.as_string())

        smtpObj.quit()
        print('success')
    except smtplib.SMTPException as e:
        print('error', e)

if __name__ == '__main__':
    zapi = ZabbixAPI("http://******")
    zapi.login("****", "****")
    print("Connected to Zabbix API Version %s" % zapi.api_version())
    print ("begin to generate history data")
    os.chdir("/home/qiang/**")
    item_data_get()
    print ("generate data success! and begin drawing graph ")
    time.sleep(5)
    cpu_return_values = get_file_data('cpu_data.csv')
    mem_return_values = get_file_data('mem_data.csv')
    disk_return_values= get_file_data('disk_data.csv')
    cpu_return_values_avg = cpu_return_values[1]
    cpu_return_values_max = cpu_return_values[2]
    cpu_return_values_hostname = cpu_return_values[3]
    host_name_show = transfer_hostname(cpu_return_values_hostname)

    mem_return_values_avg = mem_return_values[1]
    mem_return_values_max = mem_return_values[2]

    disk_return_values_avg = disk_return_values[1]
    disk_return_values_max = disk_return_values[2]

    plt.figure(num=1,figsize=(8,6))
    plt.subplot(2, 1, 1)
    draw(plt, cpu_return_values_max, mem_return_values_max, disk_return_values_max, host_name_show,'Max Utilization(1 day)','max utilization(%)')
    plt.subplot(2, 1, 2)
    draw(plt, cpu_return_values_avg, mem_return_values_avg, disk_return_values_avg, host_name_show,'Avg Utilization(1 day)', 'avg utilization(%)')
#    plt.show()
    plt.savefig('./perf_graph.png', format='png')
    print ("draw graph success!")
    send_mail()
    print ("remove csv file")
    os.remove("cpu_data.csv")
    os.remove("disk_data.csv")
    os.remove("mem_data.csv")
    print ("send email success,end!")
    print ("anilyze end!")
